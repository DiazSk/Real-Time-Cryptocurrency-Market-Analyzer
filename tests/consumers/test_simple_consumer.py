import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.consumers.simple_consumer import MinuteAggregator, parse_trade

UTC = timezone.utc


def trade(symbol="BTC", trade_id=1, price="100", size="1", side="buy", event_time=None):
    return parse_trade(json.dumps({
        "trade_id": trade_id,
        "symbol": symbol,
        "price": price,
        "size": size,
        "side": side,
        "sequence": 1,
        "event_time": (event_time or datetime(2026, 1, 1, tzinfo=UTC)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "ingest_time": datetime(2026, 1, 1, tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }))


def test_out_of_order_trades_give_correct_open_close():
    agg = MinuteAggregator()
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    # trade_ids arrive in increasing order (Kafka partition order), but event_time
    # is not monotonic (Coinbase matching-engine timestamps can wobble slightly).
    agg.add_trade(trade(trade_id=1, price="105", event_time=base + timedelta(seconds=30)))
    agg.add_trade(trade(trade_id=2, price="100", event_time=base + timedelta(seconds=5)))  # earliest event_time
    closed = agg.add_trade(trade(trade_id=3, price="110", event_time=base + timedelta(seconds=50)))  # latest
    assert closed == []  # still inside the window, no close trigger yet

    # Force close with a next-minute trade past the 2s watermark allowance.
    closed = agg.add_trade(trade(trade_id=4, price="120", event_time=base + timedelta(minutes=1, seconds=3)))
    assert len(closed) == 1
    w = closed[0]
    assert w.open == Decimal("100")   # earliest event_time, not first-arrived
    assert w.close == Decimal("110")  # latest event_time
    assert w.high == Decimal("110")   # the trigger trade (120) belongs to the next window
    assert w.low == Decimal("100")


def test_high_low_and_vwap_and_volume():
    agg = MinuteAggregator()
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    agg.add_trade(trade(trade_id=1, price="100", size="2", event_time=base))
    agg.add_trade(trade(trade_id=2, price="90", size="1", event_time=base + timedelta(seconds=10)))
    agg.add_trade(trade(trade_id=3, price="110", size="3", event_time=base + timedelta(seconds=20)))
    closed = agg.add_trade(trade(trade_id=4, price="1", event_time=base + timedelta(minutes=1, seconds=3)))
    assert len(closed) == 1
    w = closed[0]
    assert w.high == Decimal("110")
    assert w.low == Decimal("90")
    assert w.volume == Decimal("6")
    quote = Decimal("100") * 2 + Decimal("90") * 1 + Decimal("110") * 3
    assert w.quote_volume == quote
    assert w.vwap == quote / Decimal("6")
    assert w.trade_count == 3


def test_dedup_by_last_seen_trade_id():
    agg = MinuteAggregator()
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    agg.add_trade(trade(trade_id=5, price="100", event_time=base))
    agg.add_trade(trade(trade_id=5, price="999", event_time=base + timedelta(seconds=1)))  # duplicate id, dropped
    agg.add_trade(trade(trade_id=3, price="999", event_time=base + timedelta(seconds=2)))  # older id, dropped
    closed = agg.add_trade(trade(trade_id=6, price="200", event_time=base + timedelta(minutes=1, seconds=3)))
    assert len(closed) == 1
    assert closed[0].close == Decimal("100")
    assert closed[0].trade_count == 1


def test_window_closes_on_later_minute_trade():
    agg = MinuteAggregator()
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    agg.add_trade(trade(trade_id=1, event_time=base))
    closed = agg.add_trade(trade(trade_id=2, event_time=base + timedelta(minutes=2)))
    assert len(closed) == 1
    assert closed[0].window_start == base


def test_window_not_closed_within_watermark_allowance():
    agg = MinuteAggregator()
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    agg.add_trade(trade(trade_id=1, event_time=base))
    # 1 second past window_end, still under the 2s allowance.
    closed = agg.add_trade(trade(trade_id=2, event_time=base + timedelta(minutes=1, seconds=1)))
    assert closed == []


def test_flush_closes_by_wall_clock():
    agg = MinuteAggregator()
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    agg.add_trade(trade(trade_id=1, event_time=base))
    assert agg.flush(base + timedelta(minutes=1, seconds=1)) == []
    closed = agg.flush(base + timedelta(minutes=1, seconds=3))
    assert len(closed) == 1
    assert closed[0].window_start == base


@pytest.mark.parametrize("bad", [
    {"price": "0"},
    {"size": "-1"},
    {"side": "short"},
    {"event_time": "2026-01-01T10:00:00"},  # no timezone
])
def test_parse_trade_rejects_invalid(bad):
    body = {
        "trade_id": 1, "symbol": "BTC", "price": "100", "size": "1", "side": "buy",
        "sequence": 1, "event_time": "2026-01-01T10:00:00.000000Z",
        "ingest_time": "2026-01-01T10:00:00.000000Z",
    }
    body.update(bad)
    with pytest.raises(ValueError):
        parse_trade(json.dumps(body))
