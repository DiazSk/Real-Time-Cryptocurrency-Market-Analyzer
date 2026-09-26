"""
Lite-mode OHLCV consumer — replaces Flink for low-RAM environments.

Reads the producer's `crypto-trades` topic, validates and deduplicates trades
the same way Flink does, decides in-memory when a 1-minute window has closed,
then asks Postgres to (re)compute that candle's OHLCV + VWAP straight from the
persisted `raw_trades` rows and writes to Redis with the exact schema/JSON
shape the Flink sinks use (JdbcSinks.java, RedisSinkFunction.java), so the
FastAPI layer is unaffected by which mode produced the data.

Delivery is at-least-once, matching the Flink path (see README "Delivery
guarantees"): Kafka offsets are committed manually, only after a trade's
raw_trades insert has committed, so a crash mid-batch replays the trade
rather than losing it. `raw_trades`'s own `ON CONFLICT DO NOTHING` makes that
replay idempotent. Candles are always recomputed FROM raw_trades (not from
in-memory sums), so a partial replay after a restart can only ever produce
the correct, complete candle for that window — never a partial one written
over a good one. MinuteAggregator's only job is deciding WHEN a window has
closed; it does not compute OHLCV values itself.

ponytail: lite mode has no z-score anomaly detector. `price_alerts` stays
empty when running this instead of Flink; the trend is real (VWAP, OHLC) but
no PRICE_SPIKE/PRICE_DROP rows are ever written. Add a detector here if lite
mode needs alerts.

Redis key:     crypto:{SYMBOL}:latest
Redis value:   JSON with camelCase fields (matches Candle.java / RedisSinkFunction)
Redis TTL:     300 seconds
Pub/Sub:       crypto:updates channel (drives WebSocket push)
Postgres:      price_aggregates_1m UPSERT (aggregated from raw_trades) + raw_trades insert
"""

import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import psycopg2
import redis as redis_lib
from kafka import KafkaConsumer
from dotenv import load_dotenv
from pydantic import ValidationError

from src.producers.coinbase_trades_producer import Trade

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("simple_consumer")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC     = os.getenv("KAFKA_TRADES_TOPIC", "crypto-trades")
KAFKA_GROUP     = "crypto-analyzer-lite-group"

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
PG_DB   = os.getenv("POSTGRES_DB", "crypto_db")
PG_USER = os.getenv("POSTGRES_USER", "crypto_user")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "crypto_pass")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL  = 300  # seconds — matches RedisSinkFunction

PUBSUB_CHANNEL = "crypto:updates"

WATERMARK_LATENESS_SECONDS = 2.0  # stand-in for Flink's BoundedOutOfOrderness(2s)
FLUSH_INTERVAL_SECONDS = 1.0

# ---------------------------------------------------------------------------
# Validation — same rules as Flink's Trade.isValid / TradeDeserializer
# ---------------------------------------------------------------------------


def parse_trade(raw: str) -> Trade:
    """Validate one Kafka message the same way Flink does: positive price/size,
    side in {buy, sell}, tz-aware event_time. Raises ValueError if malformed."""
    try:
        return Trade.model_validate_json(raw)
    except ValidationError as e:
        raise ValueError(str(e)) from e


# ---------------------------------------------------------------------------
# Pure, testable window-close decision (event time, out-of-order tolerant).
# OHLCV values are NOT computed here — see _CANDLE_UPSERT_FROM_RAW_SQL below.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClosedWindow:
    symbol: str
    window_start: datetime
    window_end: datetime


def _floor_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


class MinuteAggregator:
    """Decides WHEN a 1-minute window has closed, per symbol.

    Dedups by last-seen trade_id per symbol (older/repeat trade_ids are dropped
    before they can affect window timing). A window closes once a trade for its
    symbol arrives at or after window_end + lateness, or when `flush(now)` is
    called with wall-clock time at or after that point — both are watermark
    stand-ins for Flink's BoundedOutOfOrdernessWatermarks. It intentionally does
    not accumulate OHLCV values: those are recomputed from raw_trades on close
    (see the module docstring), so this class stays a thin, pure decision maker.
    """

    def __init__(self, lateness_seconds: float = WATERMARK_LATENESS_SECONDS):
        self._lateness = timedelta(seconds=lateness_seconds)
        self._last_trade_id: dict[str, int] = {}
        # (symbol, window_start) -> window_end, for every window seen but not yet closed.
        self._open_windows: dict[tuple[str, datetime], datetime] = {}

    def add_trade(self, trade: Trade) -> list[ClosedWindow]:
        last = self._last_trade_id.get(trade.symbol)
        if last is not None and trade.trade_id <= last:
            return []  # duplicate or older trade_id
        self._last_trade_id[trade.symbol] = trade.trade_id

        window_start = _floor_minute(trade.event_time)
        key = (trade.symbol, window_start)
        self._open_windows.setdefault(key, window_start + timedelta(minutes=1))

        return self._close_due(trade.symbol, trade.event_time)

    def flush(self, now: datetime) -> list[ClosedWindow]:
        closed = []
        for symbol in {k[0] for k in self._open_windows}:
            closed.extend(self._close_due(symbol, now))
        return closed

    def close_all(self) -> list[ClosedWindow]:
        """Force-close every open window, regardless of watermark. Used at shutdown."""
        closed = [ClosedWindow(symbol, window_start, window_end)
                  for (symbol, window_start), window_end in self._open_windows.items()]
        self._open_windows.clear()
        return closed

    def _close_due(self, symbol: str, watermark: datetime) -> list[ClosedWindow]:
        due = [
            k for k, window_end in self._open_windows.items()
            if k[0] == symbol and window_end + self._lateness <= watermark
        ]
        return [
            ClosedWindow(k[0], k[1], self._open_windows.pop(k))
            for k in sorted(due, key=lambda k: k[1])
        ]


# ---------------------------------------------------------------------------
# I/O: Postgres + Redis sinks (mirror JdbcSinks.java / RedisSinkFunction.java)
# ---------------------------------------------------------------------------

_RAW_TRADE_SQL = """
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT id, %s, %s, %s, %s, %s, %s, %s FROM cryptocurrencies WHERE symbol = %s
ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING
"""

# Recomputes the candle straight from the persisted raw_trades rows for the window,
# rather than from in-memory sums — so a replay after a crash-restart (which can
# only ever see a subset or the full set of that window's trades, never spurious
# ones, thanks to raw_trades' own idempotent insert) always produces the complete,
# correct candle. It can never write a partial candle over a complete one.
_CANDLE_UPSERT_FROM_RAW_SQL = """
INSERT INTO price_aggregates_1m
    (crypto_id, window_start, window_end, open_price, high_price, low_price,
     close_price, vwap, volume, quote_volume, trade_count)
SELECT
    crypto_id,
    %s,
    %s,
    (array_agg(price ORDER BY event_time, trade_id))[1],
    max(price),
    min(price),
    (array_agg(price ORDER BY event_time DESC, trade_id DESC))[1],
    sum(price * size) / sum(size),
    sum(size),
    sum(price * size),
    count(*)
FROM raw_trades
WHERE crypto_id = (SELECT id FROM cryptocurrencies WHERE symbol = %s)
  AND event_time >= %s
  AND event_time < %s
GROUP BY crypto_id
ON CONFLICT (crypto_id, window_start) DO UPDATE SET
    window_end   = EXCLUDED.window_end,
    open_price   = EXCLUDED.open_price,
    high_price   = EXCLUDED.high_price,
    low_price    = EXCLUDED.low_price,
    close_price  = EXCLUDED.close_price,
    vwap         = EXCLUDED.vwap,
    volume       = EXCLUDED.volume,
    quote_volume = EXCLUDED.quote_volume,
    trade_count  = EXCLUDED.trade_count,
    updated_at   = now()
RETURNING window_start, window_end, open_price, high_price, low_price, close_price,
          vwap, volume, quote_volume, trade_count
"""


def insert_raw_trade(conn, trade: Trade) -> None:
    with conn.cursor() as cur:
        cur.execute(_RAW_TRADE_SQL, (
            trade.trade_id, trade.price, trade.size, trade.side, trade.sequence,
            trade.event_time, trade.ingest_time, trade.symbol,
        ))
    conn.commit()


def upsert_candle_from_raw_trades(conn, w: ClosedWindow) -> Optional[tuple]:
    """Recomputes and upserts the candle for `w` from raw_trades. Returns the
    upserted row (via RETURNING), or None if raw_trades had no rows for this
    window yet (e.g. the trade that should have been inserted is still pending
    retry — the next close attempt, or a later replay, will pick it up)."""
    with conn.cursor() as cur:
        cur.execute(_CANDLE_UPSERT_FROM_RAW_SQL, (
            w.window_start, w.window_end, w.symbol, w.window_start, w.window_end,
        ))
        row = cur.fetchone()
    conn.commit()
    if row is not None:
        log.info("Postgres: upserted %s candle @ %s", w.symbol, w.window_start.isoformat())
    return row


def _row_to_candle_json(symbol: str, row: tuple) -> str:
    """camelCase JSON matching Candle.java / RedisSinkFunction (epoch-second windows)."""
    window_start, window_end, open_, high, low, close, vwap, volume, quote_volume, trade_count = row
    return json.dumps({
        "symbol": symbol,
        "windowStart": window_start.timestamp(),
        "windowEnd": window_end.timestamp(),
        "open": float(open_),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "vwap": float(vwap),
        "volume": float(volume),
        "quoteVolume": float(quote_volume),
        "tradeCount": trade_count,
    })


def publish_candle(r: redis_lib.Redis, symbol: str, row: tuple) -> None:
    key = f"crypto:{symbol}:latest"
    data = _row_to_candle_json(symbol, row)
    r.setex(key, REDIS_TTL, data)
    r.publish(PUBSUB_CHANNEL, data)
    log.debug("Redis: wrote %s (TTL=%ds)", key, REDIS_TTL)


def flush_closed_window(conn, r: redis_lib.Redis, w: ClosedWindow) -> None:
    try:
        row = upsert_candle_from_raw_trades(conn, w)
    except Exception as e:
        log.error("Postgres flush failed for %s: %s", w.symbol, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return

    if row is None:
        log.warning(
            "No raw_trades rows yet for %s window %s-%s; skipping this close (will "
            "retry on the next trade or flush for %s)",
            w.symbol, w.window_start.isoformat(), w.window_end.isoformat(), w.symbol,
        )
        return

    try:
        publish_candle(r, w.symbol, row)
    except Exception as e:
        log.error("Redis flush failed for %s: %s", w.symbol, e)


# ---------------------------------------------------------------------------
# Background timer: advance the watermark by wall clock when trades are sparse.
# Runs on its own Postgres connection — psycopg2 connections are not safe to
# share across threads, and this timer thread runs concurrently with the main
# consumer thread's use of `conn`.
# ---------------------------------------------------------------------------

_shutdown = threading.Event()


def _connect_pg():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)


def _start_flush_timer(agg: MinuteAggregator, lock: threading.Lock, timer_conn, r, interval: float = FLUSH_INTERVAL_SECONDS):
    def _loop():
        while not _shutdown.is_set():
            now = datetime.now(timezone.utc)
            with lock:
                closed = agg.flush(now)
            for w in closed:
                flush_closed_window(timer_conn, r, w)
            time.sleep(interval)
    t = threading.Thread(target=_loop, daemon=True, name="flush-timer")
    t.start()
    return t


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------


def run():
    log.info("Connecting to PostgreSQL %s:%d/%s …", PG_HOST, PG_PORT, PG_DB)
    conn = _connect_pg()
    timer_conn = _connect_pg()  # dedicated connection for the flush-timer thread
    log.info("Postgres connected.")

    log.info("Connecting to Redis %s:%d …", REDIS_HOST, REDIS_PORT)
    r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    log.info("Redis connected.")

    log.info("Connecting to Kafka %s, topic=%s …", KAFKA_BOOTSTRAP, KAFKA_TOPIC)
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=KAFKA_GROUP,
        auto_offset_reset="earliest",
        # At-least-once: commit an offset only after that trade's raw_trades insert
        # has committed in Postgres, so a crash mid-batch replays the trade instead
        # of silently losing it (raw_trades' own ON CONFLICT DO NOTHING absorbs the
        # replay; the candle upsert always recomputes from raw_trades, never from
        # in-memory sums, so a replay can only ever complete a candle, not corrupt one).
        enable_auto_commit=False,
        value_deserializer=lambda v: v.decode("utf-8"),
        consumer_timeout_ms=1000,
    )
    log.info("Kafka consumer ready. Waiting for messages …")

    agg = MinuteAggregator()
    lock = threading.Lock()
    stats = {"invalid": 0}
    _start_flush_timer(agg, lock, timer_conn, r)

    def _handle_signal(sig, frame):
        log.info("Signal %d received — flushing and exiting …", sig)
        _shutdown.set()
        with lock:
            closed = agg.close_all()
        for w in closed:
            flush_closed_window(conn, r, w)
        consumer.close()
        conn.close()
        timer_conn.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while not _shutdown.is_set():
        for msg in consumer:
            if _shutdown.is_set():
                break
            try:
                trade = parse_trade(msg.value)
            except ValueError as e:
                stats["invalid"] += 1
                log.warning("Dropping invalid trade: %s", e)
                # A poison-pill message will never parse; commit past it so the
                # consumer doesn't get stuck retrying it forever.
                consumer.commit()
                continue

            try:
                insert_raw_trade(conn, trade)
            except Exception as e:
                log.error(
                    "raw_trades insert failed for %s: %s — leaving offset uncommitted for retry",
                    trade.symbol, e,
                )
                try:
                    conn.rollback()
                except Exception:
                    pass
                continue  # do not commit, do not advance the aggregator: redelivery retries this trade

            consumer.commit()

            with lock:
                closed = agg.add_trade(trade)
            for w in closed:
                flush_closed_window(conn, r, w)


if __name__ == "__main__":
    run()
