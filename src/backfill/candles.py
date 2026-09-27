"""Loads official Coinbase 1-minute candles into coinbase_candles_1m (90 days, then incremental)."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)

MINUTE = timedelta(minutes=1)
WINDOW = 300 * MINUTE  # one request spans [s, s + 299 min]: 300 buckets, the API maximum
HISTORY = timedelta(days=90)

SYMBOLS_SQL = "SELECT id, symbol, coinbase_product FROM cryptocurrencies WHERE is_active ORDER BY symbol"
LAST_BUCKET_SQL = "SELECT max(bucket) FROM coinbase_candles_1m WHERE crypto_id = %s"
UPSERT_SQL = """
INSERT INTO coinbase_candles_1m (crypto_id, bucket, open, high, low, close, volume) VALUES %s
ON CONFLICT (crypto_id, bucket) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
    close = EXCLUDED.close, volume = EXCLUDED.volume, loaded_at = now()
"""


def candle_windows(start, end):
    s = start
    while s < end:
        yield s, min(s + WINDOW - MINUTE, end)
        s += WINDOW


def candle_start(last_bucket, end):
    """Re-fetch the last (possibly partial) minute on resume; 90 days back on a first run."""
    return last_bucket - MINUTE if last_bucket else end - HISTORY


def parse_candle(row):
    t, low, high, open_, close, volume = row
    d = lambda x: Decimal(str(x))  # noqa: E731 -- str() keeps the API's exact decimal digits
    return datetime.fromtimestamp(t, tz=timezone.utc), d(open_), d(high), d(low), d(close), d(volume)


def backfill_candles(conn, api, now=None):
    end = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    with conn.cursor() as cur:
        cur.execute(SYMBOLS_SQL)
        symbols = cur.fetchall()
    loaded = {}
    for crypto_id, symbol, product in symbols:
        with conn.cursor() as cur:
            cur.execute(LAST_BUCKET_SQL, (crypto_id,))
            start = candle_start(cur.fetchone()[0], end)
        n = 0
        for s, e in candle_windows(start, end):
            rows = [(crypto_id, *parse_candle(r)) for r in api.candles(product, s, e)]
            if rows:
                with conn.cursor() as cur:
                    execute_values(cur, UPSERT_SQL, rows)
                conn.commit()
                n += len(rows)
        loaded[symbol] = n
        logger.info("candles %s: %d rows from %s", symbol, n, start.isoformat())
    return loaded
