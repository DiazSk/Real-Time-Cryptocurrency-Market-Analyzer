"""
Symbol discovery + trending endpoints.

Used by the frontend to populate the symbol picker and a "trending tokens"
panel without each component needing to know the full supported-symbol list.
"""

from fastapi import APIRouter, Depends, Query, Request
from ..database import get_db
from ..registry import symbols_of
import asyncpg

router = APIRouter(tags=["Symbols"])


@router.get(
    "/symbols",
    summary="List supported symbols",
    description="Returns the configured supported-symbol allowlist with display metadata."
)
async def list_symbols(request: Request):
    symbols = symbols_of(request)
    return {
        "symbols": [
            {"symbol": s.symbol, "name": s.name, "slug": s.coingecko_id}
            for s in symbols.values()
        ],
        "count": len(symbols),
    }


@router.get(
    "/trending",
    summary="Trending symbols by 24h price change",
    description="24h change from the candles_1h continuous aggregate (real-time aggregation, so the "
                "newest bucket includes the current hour so far). Needs about 24-25 hours of candle "
                "history before results appear.",
)
async def trending_symbols(
    limit: int = Query(10, ge=1, le=50, description="Max rows to return (1-50)"),
    direction: str = Query("abs", pattern="^(abs|gainers|losers)$",
                           description="Sort: abs (biggest movers), gainers, or losers"),
    conn: asyncpg.Connection = Depends(get_db),
):
    order_clause = {
        "abs": "ABS(price_change_24h) DESC",
        "gainers": "price_change_24h DESC",
        "losers": "price_change_24h ASC",
    }[direction]

    sql = f"""
        WITH latest AS (
            SELECT DISTINCT ON (crypto_id) crypto_id, bucket, close_price
            FROM candles_1h
            WHERE bucket > now() - INTERVAL '2 days'
            ORDER BY crypto_id, bucket DESC
        ),
        day_ago AS (
            SELECT DISTINCT ON (h.crypto_id) h.crypto_id, h.close_price
            FROM candles_1h h
            JOIN latest l ON l.crypto_id = h.crypto_id
            WHERE h.bucket <= l.bucket - INTERVAL '24 hours'
              AND h.bucket >  l.bucket - INTERVAL '48 hours'
              AND h.close_price > 0
            ORDER BY h.crypto_id, h.bucket DESC
        ),
        volume AS (
            SELECT crypto_id, SUM(quote_volume) AS volume_24h
            FROM candles_1h
            WHERE bucket > now() - INTERVAL '24 hours'
            GROUP BY crypto_id
        )
        SELECT * FROM (
            SELECT c.symbol, c.name,
                   l.close_price AS price,
                   v.volume_24h,
                   (l.close_price - d.close_price) / d.close_price * 100 AS price_change_24h,
                   l.bucket + INTERVAL '1 hour' AS as_of
            FROM latest l
            JOIN day_ago d USING (crypto_id)
            JOIN cryptocurrencies c ON c.id = l.crypto_id
            LEFT JOIN volume v USING (crypto_id)
            WHERE c.is_active
        ) t
        ORDER BY {order_clause}
        LIMIT $1
    """
    rows = await conn.fetch(sql, limit)
    return {
        "direction": direction,
        "count": len(rows),
        "trending": [
            {
                "symbol": row["symbol"],
                "name": row["name"],
                "price": float(row["price"]),
                "volume_24h": float(row["volume_24h"]) if row["volume_24h"] is not None else None,
                "market_cap": None,   # not derivable from trades; kept for the frontend schema
                "price_change_24h": float(row["price_change_24h"]),
                "timestamp": row["as_of"].isoformat(),
            }
            for row in rows
        ],
    }
