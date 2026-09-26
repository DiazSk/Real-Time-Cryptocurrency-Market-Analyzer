import json
from datetime import datetime, timedelta, timezone

import pytest

from src.consumers.simple_consumer import (
    _CANDLE_UPSERT_FROM_RAW_SQL,
    MinuteAggregator,
    parse_trade,
)

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


# ---------------------------------------------------------------------------
# MinuteAggregator: decides WHEN a window closes. It no longer computes OHLCV
# values itself — the upsert SQL recomputes those from raw_trades on close, so
# a replay after a crash can never write a partial candle (see the SQL tests
# below and the at-least-once note in the module docstring).
# ---------------------------------------------------------------------------


def test_out_of_order_trades_do_not_close_the_window_early():
    agg = MinuteAggregator()
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    # trade_ids arrive in increasing order (Kafka partition order), but event_time
    # is not monotonic (Coinbase matching-engine timestamps can wobble slightly).
    agg.add_trade(trade(trade_id=1, event_time=base + timedelta(seconds=30)))
    agg.add_trade(trade(trade_id=2, event_time=base + timedelta(seconds=5)))
    closed = agg.add_trade(trade(trade_id=3, event_time=base + timedelta(seconds=50)))
    assert closed == []  # still inside the window, no close trigger yet

    # Force close with a next-minute trade past the 2s watermark allowance.
    closed = agg.add_trade(trade(trade_id=4, event_time=base + timedelta(minutes=1, seconds=3)))
    assert len(closed) == 1
    assert closed[0].symbol == "BTC"
    assert closed[0].window_start == base
    assert closed[0].window_end == base + timedelta(minutes=1)


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


def test_duplicate_trade_id_is_dropped_before_the_watermark_check():
    agg = MinuteAggregator()
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    agg.add_trade(trade(trade_id=5, event_time=base))
    # Same trade_id again, replayed with an event_time that would otherwise close
    # the window — it must be dropped before it ever reaches the watermark check.
    closed = agg.add_trade(trade(trade_id=5, event_time=base + timedelta(minutes=5)))
    assert closed == []
    # An older trade_id is dropped the same way.
    closed = agg.add_trade(trade(trade_id=3, event_time=base + timedelta(minutes=5)))
    assert closed == []


def test_close_all_force_closes_open_windows_for_shutdown():
    agg = MinuteAggregator()
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    agg.add_trade(trade(symbol="BTC", trade_id=1, event_time=base))
    agg.add_trade(trade(symbol="ETH", trade_id=1, event_time=base))
    closed = agg.close_all()
    assert {w.symbol for w in closed} == {"BTC", "ETH"}
    assert agg.close_all() == []  # nothing left to force-close


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


# ---------------------------------------------------------------------------
# The candle upsert must recompute OHLCV from raw_trades (not from in-memory
# state), so a replay after a crash-restart can never overwrite a candle with
# partial data — a static assertion on the SQL shape is enough here; the
# behavior itself needs a real Postgres, exercised outside the unit suite.
# ---------------------------------------------------------------------------


def test_candle_upsert_sql_aggregates_from_raw_trades():
    sql = _CANDLE_UPSERT_FROM_RAW_SQL
    assert "FROM raw_trades" in sql
    assert "GROUP BY crypto_id" in sql
    assert "ON CONFLICT (crypto_id, window_start) DO UPDATE" in sql
    assert "RETURNING" in sql
    # open/close must come from event-time order, not insertion order.
    assert "ORDER BY event_time, trade_id" in sql
    assert "ORDER BY event_time DESC, trade_id DESC" in sql


# ---------------------------------------------------------------------------
# process_message: never advances (commits) past a trade whose raw_trades
# insert failed. commit() with no args commits the partition's current fetch
# position — since that position already moved past this message the instant
# the Kafka iterator returned it, "roll back and continue" silently acks a
# trade that was never persisted. The fix is to retry the SAME message in
# place until the insert succeeds, and only then commit.
# ---------------------------------------------------------------------------


class _Msg:
    def __init__(self, value):
        self.value = value


def _trade_json(trade_id=1, event_time=None, **overrides):
    body = {
        "trade_id": trade_id, "symbol": "BTC", "price": "100", "size": "1", "side": "buy",
        "sequence": 1,
        "event_time": (event_time or datetime(2026, 1, 1, tzinfo=UTC)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "ingest_time": datetime(2026, 1, 1, tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    body.update(overrides)
    return json.dumps(body)


def test_process_message_retries_insert_and_commits_once_on_success():
    from src.consumers.simple_consumer import process_message

    attempts = []
    commits = []
    sleeps = []

    def insert_fn(trade):
        attempts.append(trade.trade_id)
        if len(attempts) < 3:
            raise ConnectionError("db down")

    result = process_message(
        _Msg(_trade_json(trade_id=42)), insert_fn,
        lambda: commits.append(True), lambda s: sleeps.append(s),
    )

    assert len(attempts) == 3        # failed twice, succeeded on the third
    assert commits == [True]         # committed exactly once, after success
    assert sleeps == [1.0, 2.0]      # capped exponential backoff, recorded not real
    assert result.trade_id == 42


def test_process_message_commits_past_invalid_trade_without_retrying():
    from src.consumers.simple_consumer import process_message

    insert_calls = []
    commits = []

    result = process_message(
        _Msg(_trade_json(price="0")),  # invalid: non-positive price
        lambda t: insert_calls.append(t), lambda: commits.append(True), lambda s: None,
    )

    assert insert_calls == []   # never attempted — it will never parse
    assert commits == [True]    # committed past the poison pill
    assert result is None


def test_process_message_stops_retrying_on_shutdown_without_committing():
    from src.consumers.simple_consumer import process_message

    commits = []

    result = process_message(
        _Msg(_trade_json()), lambda t: (_ for _ in ()).throw(ConnectionError("db down")),
        lambda: commits.append(True), lambda s: None,
        is_shutting_down=lambda: True,
    )

    assert result is None
    assert commits == []  # must not commit an offset for a trade that was never inserted


def test_insert_with_reconnect_replaces_a_closed_connection():
    from src.consumers.simple_consumer import _insert_with_reconnect

    class _FakeConn:
        def __init__(self, closed):
            self.closed = closed
            self.rolled_back = False

        def rollback(self):
            self.rolled_back = True

    class _FakePg:
        def __init__(self, conn):
            self.conn = conn

    broken = _FakeConn(closed=True)
    healthy = _FakeConn(closed=False)
    pg = _FakePg(broken)

    def failing_insert(conn, trade):
        raise ConnectionError("connection terminated")

    with pytest.raises(ConnectionError):
        _insert_with_reconnect(pg, object(), insert_fn=failing_insert, connect_fn=lambda: healthy)

    assert broken.rolled_back is True
    assert pg.conn is healthy  # reconnected because the old connection was closed


def test_insert_with_reconnect_keeps_connection_when_not_closed():
    from src.consumers.simple_consumer import _insert_with_reconnect

    class _FakeConn:
        def __init__(self):
            self.closed = False
            self.rolled_back = False

        def rollback(self):
            self.rolled_back = True

    class _FakePg:
        def __init__(self, conn):
            self.conn = conn

    conn = _FakeConn()
    pg = _FakePg(conn)

    def failing_insert(c, trade):
        raise ValueError("transient error")

    with pytest.raises(ValueError):
        _insert_with_reconnect(pg, object(), insert_fn=failing_insert, connect_fn=lambda: (_ for _ in ()).throw(AssertionError("should not reconnect")))

    assert conn.rolled_back is True
    assert pg.conn is conn  # unchanged: the connection itself wasn't reported closed
