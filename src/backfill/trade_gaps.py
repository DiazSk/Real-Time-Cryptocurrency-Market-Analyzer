"""Repairs raw_trades gaps (producer restarts) from the Coinbase REST trades endpoint, by trade_id.

Coinbase trade_ids rise by exactly 1 per product, so a jump is an exact list of missing trades.
Each repaired minute's candle is recomputed from raw_trades with the lite consumer's shared SQL.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from src.candle_sql import CANDLE_UPSERT_FROM_RAW_SQL

logger = logging.getLogger(__name__)

MAX_GAP = 10_000
MINUTE = timedelta(minutes=1)
# The caggs' refresh policies only look back 1-24 h, so a repair older than that must refresh them.
CAGGS = (("candles_5m", timedelta(minutes=5)), ("candles_15m", timedelta(minutes=15)), ("candles_1h", timedelta(hours=1)))

GAPS_SQL = """
SELECT g.crypto_id, c.symbol, c.coinbase_product, g.prev_id, g.trade_id
FROM (
    SELECT crypto_id, trade_id,
           lag(trade_id) OVER (PARTITION BY crypto_id ORDER BY trade_id) AS prev_id
    FROM raw_trades
    WHERE event_time > now() - INTERVAL '7 days'
) g
JOIN cryptocurrencies c ON c.id = g.crypto_id
WHERE g.trade_id - g.prev_id > 1
ORDER BY c.symbol, g.prev_id
"""

INSERT_SQL = """
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time, source)
VALUES (%s, %s, %s, %s, %s, %s, %s, now(), 'rest_backfill')
ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING
"""


def select_missing(page, prev_id, next_id):
    return [t for t in page if prev_id < t["trade_id"] < next_id]


def fetch_gap(api, product, prev_id, next_id):
    found, after = [], next_id
    while after is not None:
        page, cursor = api.trades_page(product, after)
        found += select_missing(page, prev_id, next_id)
        if not page or min(t["trade_id"] for t in page) <= prev_id + 1 or cursor is None or cursor >= after:
            break
        after = cursor
    return found


def _row(crypto_id, t):
    event_time = datetime.fromisoformat(t["time"].replace("Z", "+00:00"))
    # REST `side` is the maker side, the same meaning as the matches channel: stored unchanged.
    return (crypto_id, t["trade_id"], Decimal(t["price"]), Decimal(t["size"]), t["side"], None, event_time)


def refresh_aggregates(conn, lo, hi):
    """Re-materialize the 5m/15m/1h rollups over [lo, hi], padded by one bucket on each side."""
    conn.autocommit = True  # CALL refresh_continuous_aggregate can't run inside a transaction block
    try:
        with conn.cursor() as cur:
            for name, width in CAGGS:
                cur.execute(f"CALL refresh_continuous_aggregate('{name}', %s, %s)", (lo - width, hi + width))
    finally:
        conn.autocommit = False


def repair_gaps(conn, api):
    repaired_minutes = []
    report = {"gaps_found": 0, "gaps_repaired": 0, "gaps_skipped": 0, "trades_inserted": 0, "minutes_recomputed": 0}
    with conn.cursor() as cur:
        cur.execute(GAPS_SQL)
        gaps = cur.fetchall()
    for crypto_id, symbol, product, prev_id, next_id in gaps:
        report["gaps_found"] += 1
        missing = next_id - prev_id - 1
        if missing > MAX_GAP:
            logger.warning("%s: gap of %d trades after %d exceeds %d; skipped", symbol, missing, prev_id, MAX_GAP)
            report["gaps_skipped"] += 1
            continue
        rows = [_row(crypto_id, t) for t in fetch_gap(api, product, prev_id, next_id)]
        minutes = sorted({r[6].replace(second=0, microsecond=0) for r in rows})
        with conn.cursor() as cur:
            if rows:
                cur.executemany(INSERT_SQL, rows)
            for m in minutes:
                cur.execute(CANDLE_UPSERT_FROM_RAW_SQL, (m, m + MINUTE, symbol, m, m + MINUTE))
        conn.commit()
        report["trades_inserted"] += len(rows)
        report["minutes_recomputed"] += len(minutes)
        repaired_minutes += minutes
        if len(rows) == missing:
            report["gaps_repaired"] += 1
        else:
            logger.warning("%s: gap after %d: fetched %d of %d missing trades", symbol, prev_id, len(rows), missing)
    if repaired_minutes:
        refresh_aggregates(conn, min(repaired_minutes), max(repaired_minutes) + MINUTE)
    logger.info("trade gaps: %s", report)
    return report
