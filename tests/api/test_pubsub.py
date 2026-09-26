import asyncio
import json

from src.api.pubsub import PubSubDispatcher


class FakePubSub:
    def __init__(self, messages):
        self._messages = messages
        self.subscribed = None
        self.unsubscribed = None
        self.closed = False

    async def subscribe(self, *channels):
        self.subscribed = channels

    async def listen(self):
        for m in self._messages:
            yield m
        # Block "forever" (until the task is cancelled) so the task doesn't finish early.
        await asyncio.sleep(3600)

    async def unsubscribe(self, *channels):
        self.unsubscribed = channels

    async def aclose(self):
        self.closed = True


class FakeRedisClient:
    def __init__(self, messages):
        self.fake_pubsub = FakePubSub(messages)

    def pubsub(self):
        return self.fake_pubsub


def test_dispatcher_delivers_channel_and_parsed_data_to_handlers():
    messages = [
        {"type": "subscribe", "channel": "crypto:updates", "data": 1},  # ignored, not a "message"
        {"type": "message", "channel": "crypto:updates", "data": json.dumps({"symbol": "BTC"})},
        {"type": "message", "channel": "crypto:trades", "data": json.dumps({"symbol": "ETH", "price": 1.0})},
    ]
    redis_client = FakeRedisClient(messages)
    dispatcher = PubSubDispatcher()
    received = []

    async def handler(channel, data):
        received.append((channel, data))

    dispatcher.add_handler(handler)

    async def scenario():
        dispatcher.start(redis_client)
        await asyncio.sleep(0.05)
        assert dispatcher.is_running
        await dispatcher.stop()

    asyncio.run(scenario())

    assert received == [
        ("crypto:updates", {"symbol": "BTC"}),
        ("crypto:trades", {"symbol": "ETH", "price": 1.0}),
    ]
    assert not dispatcher.is_running
    assert redis_client.fake_pubsub.subscribed == ("crypto:updates", "crypto:trades")
    assert redis_client.fake_pubsub.closed


def test_start_is_idempotent_and_stop_is_safe_when_never_started():
    dispatcher = PubSubDispatcher()

    async def scenario():
        assert not dispatcher.is_running
        await dispatcher.stop()  # must not raise

        redis_client = FakeRedisClient([])
        dispatcher.start(redis_client)
        first_task = dispatcher._task
        dispatcher.start(redis_client)  # no-op while already running
        assert dispatcher._task is first_task
        await dispatcher.stop()

    asyncio.run(scenario())


def test_bad_json_payload_is_dropped_not_raised():
    messages = [{"type": "message", "channel": "crypto:updates", "data": "not json"}]
    redis_client = FakeRedisClient(messages)
    dispatcher = PubSubDispatcher()
    received = []

    async def handler(channel, data):
        received.append((channel, data))

    dispatcher.add_handler(handler)

    async def scenario():
        dispatcher.start(redis_client)
        await asyncio.sleep(0.05)
        await dispatcher.stop()

    asyncio.run(scenario())
    assert received == []
