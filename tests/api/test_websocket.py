import asyncio

from src.api.endpoints.websocket import ConnectionManager
from src.api.pubsub import pubsub_dispatcher


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, message):
        self.sent.append(message)


def test_trade_message_reaches_symbol_and_all_subscribers():
    manager = ConnectionManager()
    btc_ws = FakeWebSocket()
    all_ws = FakeWebSocket()
    manager.connections["BTC"] = {btc_ws}
    manager.connections["ALL"] = {all_ws}

    asyncio.run(manager.handle_message("crypto:trades", {"symbol": "BTC", "price": 100.5, "time": 123.0}))

    for ws in (btc_ws, all_ws):
        assert len(ws.sent) == 1
        assert ws.sent[0] == {"type": "trade", "symbol": "BTC", "price": 100.5, "time": 123.0}


def test_trade_message_for_other_symbol_does_not_reach_subscriber():
    manager = ConnectionManager()
    eth_ws = FakeWebSocket()
    manager.connections["ETH"] = {eth_ws}
    manager.connections["ALL"] = set()

    asyncio.run(manager.handle_message("crypto:trades", {"symbol": "BTC", "price": 1.0, "time": 1.0}))

    assert eth_ws.sent == []


def test_candle_message_still_produces_price_update():
    manager = ConnectionManager()
    ws = FakeWebSocket()
    manager.connections["BTC"] = {ws}
    manager.connections["ALL"] = set()
    candle = {
        "symbol": "BTC", "windowStart": 1.0, "windowEnd": 61.0,
        "open": 1, "high": 1, "low": 1, "close": 1, "vwap": 1,
        "volume": 1, "quoteVolume": 1, "tradeCount": 1,
    }

    asyncio.run(manager.handle_message("crypto:updates", candle))

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "price_update"
    assert ws.sent[0]["symbol"] == "BTC"
    assert ws.sent[0]["data"] == candle


def test_manager_handle_message_is_registered_on_the_shared_dispatcher():
    from src.api.endpoints.websocket import manager
    assert manager.handle_message in pubsub_dispatcher._handlers


def test_ws_stats_reports_pubsub_active(fakes):
    client, _, _ = fakes

    class _FakePubSub:
        async def subscribe(self, *a):
            pass

        async def listen(self):
            await asyncio.sleep(3600)

        async def unsubscribe(self, *a):
            pass

        async def aclose(self):
            pass

    class _FakeRedis:
        def pubsub(self):
            return _FakePubSub()

    async def scenario():
        pubsub_dispatcher.start(_FakeRedis())
        try:
            r = client.get("/ws/stats")
            assert r.json()["pubsub_active"] is True
        finally:
            await pubsub_dispatcher.stop()
        r = client.get("/ws/stats")
        assert r.json()["pubsub_active"] is False

    asyncio.run(scenario())
