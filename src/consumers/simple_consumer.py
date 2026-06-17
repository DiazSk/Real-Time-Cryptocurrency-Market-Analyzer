"""
Lite-mode OHLC consumer — replaces Flink for low-RAM environments.

Reads from Kafka crypto-prices topic, computes 1-minute OHLC candles
per symbol, and writes to PostgreSQL + Redis with the same key/schema
that RedisSinkFunction.java uses, so the FastAPI layer is unaffected.

Redis key:     crypto:{SYMBOL}:latest
Redis value:   JSON with camelCase fields (matches OHLCCandle.java)
Redis TTL:     300 seconds
Pub/Sub:       crypto:updates channel (drives WebSocket push)
Postgres:      price_aggregates_1m UPSERT (crypto_id, window_start)
"""

import json
import logging
import os
import signal
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

import psycopg2
import psycopg2.extras
import redis as redis_lib
from kafka import KafkaConsumer
from dotenv import load_dotenv

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
KAFKA_TOPIC     = os.getenv("KAFKA_TOPIC", "crypto-prices")
KAFKA_GROUP     = "crypto-analyzer-lite-group"

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
PG_DB   = os.getenv("POSTGRES_DB", "crypto_db")
PG_USER = os.getenv("POSTGRES_USER", "crypto_user")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "crypto_pass")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL  = 300  # seconds — matches RedisSinkFunction default

# Symbol → DB crypto_id (must match init-db.sql INSERT order)
CRYPTO_ID_MAP = {
    "BTC":   1,
    "ETH":   2,
    "SOL":   3,
    "XRP":   4,
    "ADA":   5,
    "DOGE":  6,
    "AVAX":  7,
    "MATIC": 8,
}

PUBSUB_CHANNEL = "crypto:updates"

# ---------------------------------------------------------------------------
# OHLC accumulator
# ---------------------------------------------------------------------------

class OHLCAccumulator:
    __slots__ = ("symbol", "window_start", "window_end",
                 "open", "high", "low", "close",
                 "volume_sum", "event_count")

    def __init__(self, symbol: str, window_start: datetime, price: float, volume: float):
        self.symbol       = symbol
        self.window_start = window_start
        self.window_end   = window_start + timedelta(minutes=1)
        self.open         = price
        self.high         = price
        self.low          = price
        self.close        = price
        self.volume_sum   = volume
        self.event_count  = 1

    def update(self, price: float, volume: float) -> None:
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close       = price
        self.volume_sum += volume
        self.event_count += 1

    def to_redis_json(self) -> str:
        """Produce camelCase JSON matching Flink OHLCCandle serialization."""
        return json.dumps({
            "symbol":      self.symbol,
            "windowStart": self.window_start.timestamp(),
            "windowEnd":   self.window_end.timestamp(),
            "open":        self.open,
            "high":        self.high,
            "low":         self.low,
            "close":       self.close,
            "volumeSum":   self.volume_sum,
            "eventCount":  self.event_count,
        })


def _floor_to_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Flush helpers
# ---------------------------------------------------------------------------

def flush_to_redis(r: redis_lib.Redis, acc: OHLCAccumulator) -> None:
    key  = f"crypto:{acc.symbol}:latest"
    data = acc.to_redis_json()
    r.setex(key, REDIS_TTL, data)
    r.publish(PUBSUB_CHANNEL, data)
    log.debug("Redis: wrote %s (TTL=%ds)", key, REDIS_TTL)


_UPSERT_SQL = """
INSERT INTO price_aggregates_1m
    (crypto_id, window_start, window_end,
     open_price, high_price, low_price, close_price, avg_price,
     volume_sum, trade_count)
VALUES
    (%(crypto_id)s, %(window_start)s, %(window_end)s,
     %(open)s, %(high)s, %(low)s, %(close)s, %(avg)s,
     %(volume_sum)s, %(trade_count)s)
ON CONFLICT (crypto_id, window_start) DO UPDATE SET
    window_end   = EXCLUDED.window_end,
    open_price   = EXCLUDED.open_price,
    high_price   = EXCLUDED.high_price,
    low_price    = EXCLUDED.low_price,
    close_price  = EXCLUDED.close_price,
    avg_price    = EXCLUDED.avg_price,
    volume_sum   = EXCLUDED.volume_sum,
    trade_count  = EXCLUDED.trade_count
"""


def flush_to_postgres(conn, acc: OHLCAccumulator) -> None:
    crypto_id = CRYPTO_ID_MAP.get(acc.symbol)
    if crypto_id is None:
        log.warning("Unknown symbol %s — skipping Postgres write", acc.symbol)
        return
    avg = (acc.open + acc.high + acc.low + acc.close) / 4.0
    with conn.cursor() as cur:
        cur.execute(_UPSERT_SQL, {
            "crypto_id":    crypto_id,
            "window_start": acc.window_start,
            "window_end":   acc.window_end,
            "open":         acc.open,
            "high":         acc.high,
            "low":          acc.low,
            "close":        acc.close,
            "avg":          avg,
            "volume_sum":   acc.volume_sum,
            "trade_count":  acc.event_count,
        })
    conn.commit()
    log.info("Postgres: upserted %s candle @ %s", acc.symbol, acc.window_start.isoformat())


def flush_window(acc: OHLCAccumulator, r: redis_lib.Redis, conn) -> None:
    try:
        flush_to_redis(r, acc)
    except Exception as e:
        log.error("Redis flush failed for %s: %s", acc.symbol, e)
    try:
        flush_to_postgres(conn, acc)
    except Exception as e:
        log.error("Postgres flush failed for %s: %s", acc.symbol, e)
        try:
            conn.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Background timer: flush windows that closed more than 5s ago
# ---------------------------------------------------------------------------

_shutdown = threading.Event()


def _start_flush_timer(windows: dict, r: redis_lib.Redis, conn, interval: float = 5.0):
    def _loop():
        while not _shutdown.is_set():
            now = datetime.now(timezone.utc)
            stale = [
                (sym, acc) for sym, acc in list(windows.items())
                if acc.window_end <= now - timedelta(seconds=5)
            ]
            for sym, acc in stale:
                log.info("Timer flush: %s window %s–%s (%d events)",
                         sym, acc.window_start.isoformat(), acc.window_end.isoformat(), acc.event_count)
                flush_window(acc, r, conn)
                del windows[sym]
            time.sleep(interval)
    t = threading.Thread(target=_loop, daemon=True, name="flush-timer")
    t.start()
    return t


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------

def _parse_message(raw: str) -> Optional[dict]:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        log.warning("Bad JSON: %s — %s", raw[:80], e)
        return None


def run():
    log.info("Connecting to PostgreSQL %s:%d/%s …", PG_HOST, PG_PORT, PG_DB)
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )
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

    # Per-symbol current-window accumulator
    windows: dict[str, OHLCAccumulator] = {}

    _start_flush_timer(windows, r, conn)

    def _handle_signal(sig, frame):
        log.info("Signal %d received — flushing and exiting …", sig)
        _shutdown.set()
        # Flush all open windows on shutdown
        for acc in list(windows.values()):
            flush_window(acc, r, conn)
        consumer.close()
        conn.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while not _shutdown.is_set():
        for msg in consumer:
            if _shutdown.is_set():
                break
            data = _parse_message(msg.value)
            if data is None:
                continue

            symbol = str(data.get("symbol", "")).upper()
            if symbol not in CRYPTO_ID_MAP:
                continue

            try:
                price  = float(data["price_usd"])
                volume = float(data.get("volume_24h", 0.0))
            except (KeyError, TypeError, ValueError) as e:
                log.warning("Skipping malformed message for %s: %s", symbol, e)
                continue

            # Parse event timestamp
            raw_ts = data.get("timestamp") or data.get("last_updated")
            try:
                if isinstance(raw_ts, str):
                    ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                elif isinstance(raw_ts, (int, float)):
                    ts = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
                else:
                    ts = datetime.now(timezone.utc)
            except (ValueError, OSError):
                ts = datetime.now(timezone.utc)

            window_start = _floor_to_minute(ts)

            if symbol in windows:
                acc = windows[symbol]
                if window_start > acc.window_start:
                    # New window opened — flush the old one
                    log.info("New window for %s — flushing %s (%d events)",
                             symbol, acc.window_start.isoformat(), acc.event_count)
                    flush_window(acc, r, conn)
                    windows[symbol] = OHLCAccumulator(symbol, window_start, price, volume)
                else:
                    acc.update(price, volume)
            else:
                windows[symbol] = OHLCAccumulator(symbol, window_start, price, volume)


if __name__ == "__main__":
    run()
