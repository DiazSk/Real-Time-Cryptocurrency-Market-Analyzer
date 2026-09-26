"""
Lite-mode OHLCV consumer — replaces Flink for low-RAM environments.

Reads the producer's `crypto-trades` topic, validates and deduplicates trades
the same way Flink does, aggregates real 1-minute OHLCV + VWAP candles by
event time, and writes to PostgreSQL + Redis with the exact schema/JSON shape
the Flink sinks use (JdbcSinks.java, RedisSinkFunction.java), so the FastAPI
layer is unaffected by which mode produced the data.

ponytail: lite mode has no z-score anomaly detector. `price_alerts` stays
empty when running this instead of Flink; the trend is real (VWAP, OHLC) but
no PRICE_SPIKE/PRICE_DROP rows are ever written. Add a detector here if lite
mode needs alerts.

Redis key:     crypto:{SYMBOL}:latest
Redis value:   JSON with camelCase fields (matches Candle.java / RedisSinkFunction)
Redis TTL:     300 seconds
Pub/Sub:       crypto:updates channel (drives WebSocket push)
Postgres:      price_aggregates_1m UPSERT + raw_trades insert (matches JdbcSinks.java)
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
from decimal import Decimal
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
# Pure, testable 1-minute OHLCV aggregator (event time, out-of-order tolerant)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClosedWindow:
    symbol: str
    window_start: datetime
    window_end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal
    vwap: Decimal
    trade_count: int

    def to_redis_json(self) -> str:
        """camelCase JSON matching Candle.java / RedisSinkFunction (epoch-second windows)."""
        return json.dumps({
            "symbol": self.symbol,
            "windowStart": self.window_start.timestamp(),
            "windowEnd": self.window_end.timestamp(),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "vwap": float(self.vwap),
            "volume": float(self.volume),
            "quoteVolume": float(self.quote_volume),
            "tradeCount": self.trade_count,
        })


class _WindowAcc:
    """Mutable accumulator for one (symbol, window_start) bucket."""

    __slots__ = (
        "symbol", "window_start", "window_end", "open", "high", "low", "close",
        "volume", "quote_volume", "trade_count", "_open_key", "_close_key",
    )

    def __init__(self, symbol: str, window_start: datetime):
        self.symbol = symbol
        self.window_start = window_start
        self.window_end = window_start + timedelta(minutes=1)
        self.open = self.high = self.low = self.close = None
        self.volume = Decimal(0)
        self.quote_volume = Decimal(0)
        self.trade_count = 0
        self._open_key = None
        self._close_key = None

    def merge(self, trade: Trade) -> None:
        key = (trade.event_time, trade.trade_id)
        if self._open_key is None or key < self._open_key:
            self._open_key = key
            self.open = trade.price
        if self._close_key is None or key > self._close_key:
            self._close_key = key
            self.close = trade.price
        if self.high is None or trade.price > self.high:
            self.high = trade.price
        if self.low is None or trade.price < self.low:
            self.low = trade.price
        self.volume += trade.size
        self.quote_volume += trade.price * trade.size
        self.trade_count += 1

    def to_closed_window(self) -> ClosedWindow:
        return ClosedWindow(
            symbol=self.symbol, window_start=self.window_start, window_end=self.window_end,
            open=self.open, high=self.high, low=self.low, close=self.close,
            volume=self.volume, quote_volume=self.quote_volume,
            vwap=self.quote_volume / self.volume, trade_count=self.trade_count,
        )


def _floor_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


class MinuteAggregator:
    """Real 1-minute OHLCV + VWAP aggregation by event time, per symbol.

    Dedups by last-seen trade_id per symbol (older/repeat trade_ids are dropped).
    A window closes once a trade for its symbol arrives at or after
    window_end + lateness, or when `flush(now)` is called with wall-clock time
    at or after that point — both are watermark stand-ins for Flink's
    BoundedOutOfOrdernessWatermarks.
    """

    def __init__(self, lateness_seconds: float = WATERMARK_LATENESS_SECONDS):
        self._lateness = timedelta(seconds=lateness_seconds)
        self._last_trade_id: dict[str, int] = {}
        self._windows: dict[tuple[str, datetime], _WindowAcc] = {}

    def add_trade(self, trade: Trade) -> list[ClosedWindow]:
        last = self._last_trade_id.get(trade.symbol)
        if last is not None and trade.trade_id <= last:
            return []  # duplicate or older trade_id
        self._last_trade_id[trade.symbol] = trade.trade_id

        key = (trade.symbol, _floor_minute(trade.event_time))
        acc = self._windows.setdefault(key, _WindowAcc(*key))
        acc.merge(trade)

        return self._close_due(trade.symbol, trade.event_time)

    def flush(self, now: datetime) -> list[ClosedWindow]:
        closed = []
        for symbol in {k[0] for k in self._windows}:
            closed.extend(self._close_due(symbol, now))
        return closed

    def close_all(self) -> list[ClosedWindow]:
        """Force-close every open window, regardless of watermark. Used at shutdown."""
        closed = [acc.to_closed_window() for acc in self._windows.values()]
        self._windows.clear()
        return closed

    def _close_due(self, symbol: str, watermark: datetime) -> list[ClosedWindow]:
        due = [
            k for k, acc in self._windows.items()
            if k[0] == symbol and acc.window_end + self._lateness <= watermark
        ]
        return [self._windows.pop(k).to_closed_window() for k in sorted(due, key=lambda k: k[1])]


# ---------------------------------------------------------------------------
# I/O: Postgres + Redis sinks (mirror JdbcSinks.java / RedisSinkFunction.java)
# ---------------------------------------------------------------------------

_CANDLE_UPSERT_SQL = """
INSERT INTO price_aggregates_1m
    (crypto_id, window_start, window_end, open_price, high_price, low_price,
     close_price, vwap, volume, quote_volume, trade_count)
SELECT id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s FROM cryptocurrencies WHERE symbol = %s
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
"""

_RAW_TRADE_SQL = """
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT id, %s, %s, %s, %s, %s, %s, %s FROM cryptocurrencies WHERE symbol = %s
ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING
"""


def insert_raw_trade(conn, trade: Trade) -> None:
    with conn.cursor() as cur:
        cur.execute(_RAW_TRADE_SQL, (
            trade.trade_id, trade.price, trade.size, trade.side, trade.sequence,
            trade.event_time, trade.ingest_time, trade.symbol,
        ))
    conn.commit()


def upsert_candle(conn, w: ClosedWindow) -> None:
    with conn.cursor() as cur:
        cur.execute(_CANDLE_UPSERT_SQL, (
            w.window_start, w.window_end, w.open, w.high, w.low, w.close,
            w.vwap, w.volume, w.quote_volume, w.trade_count, w.symbol,
        ))
    conn.commit()
    log.info("Postgres: upserted %s candle @ %s", w.symbol, w.window_start.isoformat())


def publish_candle(r: redis_lib.Redis, w: ClosedWindow) -> None:
    key = f"crypto:{w.symbol}:latest"
    data = w.to_redis_json()
    r.setex(key, REDIS_TTL, data)
    r.publish(PUBSUB_CHANNEL, data)
    log.debug("Redis: wrote %s (TTL=%ds)", key, REDIS_TTL)


def flush_closed_window(conn, r: redis_lib.Redis, w: ClosedWindow) -> None:
    try:
        publish_candle(r, w)
    except Exception as e:
        log.error("Redis flush failed for %s: %s", w.symbol, e)
    try:
        upsert_candle(conn, w)
    except Exception as e:
        log.error("Postgres flush failed for %s: %s", w.symbol, e)
        try:
            conn.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Background timer: advance the watermark by wall clock when trades are sparse
# ---------------------------------------------------------------------------

_shutdown = threading.Event()


def _start_flush_timer(agg: MinuteAggregator, lock: threading.Lock, conn, r, interval: float = FLUSH_INTERVAL_SECONDS):
    def _loop():
        while not _shutdown.is_set():
            now = datetime.now(timezone.utc)
            with lock:
                closed = agg.flush(now)
            for w in closed:
                flush_closed_window(conn, r, w)
            time.sleep(interval)
    t = threading.Thread(target=_loop, daemon=True, name="flush-timer")
    t.start()
    return t


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------


def run():
    log.info("Connecting to PostgreSQL %s:%d/%s …", PG_HOST, PG_PORT, PG_DB)
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)
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
        enable_auto_commit=True,
        value_deserializer=lambda v: v.decode("utf-8"),
        consumer_timeout_ms=1000,
    )
    log.info("Kafka consumer ready. Waiting for messages …")

    agg = MinuteAggregator()
    lock = threading.Lock()
    stats = {"invalid": 0}
    _start_flush_timer(agg, lock, conn, r)

    def _handle_signal(sig, frame):
        log.info("Signal %d received — flushing and exiting …", sig)
        _shutdown.set()
        with lock:
            closed = agg.close_all()
        for w in closed:
            flush_closed_window(conn, r, w)
        consumer.close()
        conn.close()
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
                continue

            try:
                insert_raw_trade(conn, trade)
            except Exception as e:
                log.error("raw_trades insert failed for %s: %s", trade.symbol, e)
                try:
                    conn.rollback()
                except Exception:
                    pass

            with lock:
                closed = agg.add_trade(trade)
            for w in closed:
                flush_closed_window(conn, r, w)


if __name__ == "__main__":
    run()
