import asyncio
import json

import pytest
import redis.exceptions

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


class FlakyPubSub:
    """Fails once on listen(), as if the connection to Redis had dropped."""

    def __init__(self, fail: bool, error: Exception):
        self.fail = fail
        self.error = error
        self.subscribed = None
        self.closed = False

    async def subscribe(self, *channels):
        self.subscribed = channels

    async def listen(self):
        if self.fail:
            raise self.error
        yield {"type": "message", "channel": "crypto:updates", "data": '{"symbol": "BTC"}'}
        await asyncio.sleep(3600)

    async def unsubscribe(self, *channels):
        pass

    async def aclose(self):
        self.closed = True


class FlakyRedisClient:
    """First pubsub() attempt drops the connection; the second succeeds."""

    def __init__(self, error: Exception):
        self.error = error
        self.calls = 0
        self.instances = []

    def pubsub(self):
        self.calls += 1
        instance = FlakyPubSub(fail=(self.calls == 1), error=self.error)
        self.instances.append(instance)
        return instance


# redis-py's ConnectionError is not a subclass of the builtin one; a real `docker stop redis` raises it.
@pytest.mark.parametrize("error", [
    ConnectionError("connection reset by peer"),
    redis.exceptions.ConnectionError("Connection closed by server."),
    redis.exceptions.TimeoutError("Timeout reading from socket"),
])
def test_reconnects_after_connection_error_and_delivers_message(error):
    redis_client = FlakyRedisClient(error)
    dispatcher = PubSubDispatcher()
    dispatcher._sleep = lambda seconds: asyncio.sleep(0)  # skip real backoff in the test
    received = []

    async def handler(channel, data):
        received.append((channel, data))

    dispatcher.add_handler(handler)

    async def scenario():
        dispatcher.start(redis_client)
        await asyncio.sleep(0.05)
        assert dispatcher.is_running  # subscribed again after the reconnect
        await dispatcher.stop()

    asyncio.run(scenario())

    assert received == [("crypto:updates", {"symbol": "BTC"})]
    assert redis_client.calls == 2  # first attempt failed, second succeeded
    assert not dispatcher.is_running


def test_cancelled_error_exits_cleanly_during_reconnect_backoff():
    dispatcher = PubSubDispatcher()

    async def never_sleeps_real_time(seconds):
        await asyncio.sleep(3600)  # stand-in for "still backing off" when stop() is called

    dispatcher._sleep = never_sleeps_real_time
    redis_client = FlakyRedisClient(ConnectionError("reset"))  # first (only) attempt fails, then it's backing off

    async def scenario():
        dispatcher.start(redis_client)
        await asyncio.sleep(0.05)
        await dispatcher.stop()  # must return promptly, not hang for the 3600s "backoff"

    asyncio.run(scenario())
    assert not dispatcher.is_running
