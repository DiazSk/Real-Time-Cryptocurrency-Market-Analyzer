import asyncio
import importlib
import json
from datetime import datetime, timezone

import pytest

from src.producers.coinbase_trades_producer import (
    CoinbaseTradeProducer,
    FatalFeedError,
    TradeGapTracker,
    parse_match,
)
from src.symbols import Symbol

SYMBOLS = {"BTC": Symbol("BTC", "Bitcoin", "bitcoin", "BTC-USD")}
PRODUCTS = {"BTC-USD": "BTC"}
NOW = datetime(2026, 9, 26, 4, 7, 21, tzinfo=timezone.utc)


def match(**overrides) -> dict:
    """A real Coinbase `match` message (captured 2026-09-26)."""
    msg = {
        "type": "match", "trade_id": 1098679010, "maker_order_id": "m", "taker_order_id": "t",
        "side": "buy", "size": "0.00000011", "price": "83982.07", "product_id": "BTC-USD",
        "sequence": 136797320187, "time": "2026-09-26T04:07:20.310372Z",
    }
    msg.update(overrides)
    return msg


class FakeFuture:
    def add_errback(self, fn):
        return self


class FakeKafka:
    def __init__(self):
        self.sent = []

    def send(self, topic, key, value):
        self.sent.append((topic, key, value))
        return FakeFuture()


class FakeRedis:
    def __init__(self, fail=False):
        self.published = []
        self.fail = fail

    def publish(self, channel, message):
        if self.fail:
            raise ConnectionError("redis unreachable")
        self.published.append((channel, message))


@pytest.fixture
def producer():
    return CoinbaseTradeProducer(SYMBOLS, FakeKafka(), "crypto-trades")


@pytest.fixture
def redis_producer():
    r = FakeRedis()
    p = CoinbaseTradeProducer(SYMBOLS, FakeKafka(), "crypto-trades", redis_client=r)
    return p, r


def test_parse_match_maps_coinbase_fields():
    t = parse_match(match(), PRODUCTS, NOW)
    assert t.symbol == "BTC"
    assert t.trade_id == 1098679010
    assert str(t.price) == "83982.07"
    assert t.side == "buy"
    assert t.event_time == datetime(2026, 9, 26, 4, 7, 20, 310372, tzinfo=timezone.utc)


@pytest.mark.parametrize("bad", [
    {"price": "0"},
    {"size": "-1"},
    {"side": "short"},
    {"trade_id": None},
    {"time": "2026-09-26T04:07:20"},   # no timezone
    {"product_id": "SHIB-USD"},        # not tracked
])
def test_parse_match_rejects_bad_messages(bad):
    with pytest.raises(ValueError):
        parse_match(match(**bad), PRODUCTS, NOW)


def test_trade_json_uses_z_suffix_and_decimal_strings():
    body = json.loads(parse_match(match(), PRODUCTS, NOW).model_dump_json())
    assert body["event_time"] == "2026-09-26T04:07:20.310372Z"
    assert body["ingest_time"] == "2026-09-26T04:07:21.000000Z"
    assert body["price"] == "83982.07"


def test_gap_tracker_counts_missed_trades_and_flags_repeats():
    g = TradeGapTracker()
    assert g.observe("BTC", 10) == 0      # first sighting
    assert g.observe("BTC", 11) == 0
    assert g.observe("BTC", 15) == 3      # 12, 13, 14 missed
    assert g.observe("BTC", 15) is None   # repeat
    assert g.observe("BTC", 12) is None   # older than last seen
    assert g.observe("ETH", 1) == 0       # independent per symbol
    assert g.missed == 3


def test_match_is_published_keyed_by_symbol(producer):
    producer.handle_message(json.dumps(match()))
    topic, key, value = producer.kafka.sent[0]
    assert (topic, key) == ("crypto-trades", "BTC")
    assert json.loads(value)["trade_id"] == 1098679010
    assert producer.stats["published"] == 1


def test_last_match_is_a_trade_and_is_deduped(producer):
    producer.handle_message(json.dumps(match(type="last_match")))
    producer.handle_message(json.dumps(match()))  # same trade_id again, e.g. after a reconnect
    assert len(producer.kafka.sent) == 1
    assert producer.stats["duplicates"] == 1


def test_non_trade_messages_are_ignored(producer):
    producer.handle_message(json.dumps({"type": "subscriptions", "channels": []}))
    producer.handle_message(json.dumps({"type": "heartbeat"}))
    assert producer.kafka.sent == []
    assert producer.stats["invalid"] == 0


def test_invalid_trade_is_counted_not_published(producer):
    producer.handle_message(json.dumps(match(price="abc")))
    producer.handle_message("not json")
    assert producer.kafka.sent == []
    assert producer.stats["invalid"] == 2


def test_subscription_error_is_fatal(producer):
    err = {"type": "error", "message": "Failed to subscribe", "reason": "POL-USD is not a valid product"}
    with pytest.raises(FatalFeedError, match="POL-USD"):
        producer.handle_message(json.dumps(err))


def test_reconnect_backoff_doubles_then_stops_on_fatal(producer):
    outcomes = iter([OSError("reset"), OSError("reset"), FatalFeedError("bad product")])

    async def fake_stream_once():
        raise next(outcomes)

    delays = []

    async def fake_sleep(seconds):
        delays.append(seconds)

    producer.stream_once = fake_stream_once
    producer._sleep = fake_sleep
    with pytest.raises(FatalFeedError):
        asyncio.run(producer.run_forever())
    assert len(delays) == 2
    assert 1.0 <= delays[0] < 2.0   # 1 s + jitter
    assert 2.0 <= delays[1] < 3.0   # doubled
    assert producer.stats["reconnects"] == 2


def test_stale_kafka_topic_env_is_ignored(monkeypatch):
    monkeypatch.setenv("KAFKA_TOPIC", "crypto-prices")
    monkeypatch.delenv("KAFKA_TRADES_TOPIC", raising=False)
    import src.config
    assert importlib.reload(src.config).KAFKA_TOPIC_TRADES == "crypto-trades"


def test_new_trade_is_published_to_redis_trades_channel(redis_producer):
    p, r = redis_producer
    p.handle_message(json.dumps(match()))
    assert len(r.published) == 1
    channel, message = r.published[0]
    assert channel == "crypto:trades"
    body = json.loads(message)
    assert body["symbol"] == "BTC"
    assert body["price"] == 83982.07
    assert body["time"] == datetime(2026, 9, 26, 4, 7, 20, 310372, tzinfo=timezone.utc).timestamp()


def test_duplicate_trade_is_not_published_to_redis(redis_producer):
    p, r = redis_producer
    p.handle_message(json.dumps(match()))
    p.handle_message(json.dumps(match()))  # same trade_id, deduped
    assert len(r.published) == 1


def test_redis_failure_does_not_stop_kafka_publish(caplog):
    r = FakeRedis(fail=True)
    p = CoinbaseTradeProducer(SYMBOLS, FakeKafka(), "crypto-trades", redis_client=r)
    p.handle_message(json.dumps(match()))  # must not raise
    assert len(p.kafka.sent) == 1
    assert r.published == []


def test_no_redis_client_is_a_noop():
    p = CoinbaseTradeProducer(SYMBOLS, FakeKafka(), "crypto-trades")
    p.handle_message(json.dumps(match()))  # must not raise with redis_client=None
    assert len(p.kafka.sent) == 1


def test_build_redis_client_has_bounded_socket_timeouts():
    from src.producers.coinbase_trades_producer import _build_redis_client
    client = _build_redis_client()
    kwargs = client.connection_pool.connection_kwargs
    assert kwargs["socket_connect_timeout"] == 0.5
    assert kwargs["socket_timeout"] == 0.5
    assert kwargs["health_check_interval"] > 0
