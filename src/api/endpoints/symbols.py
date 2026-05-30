"""
Symbol discovery + trending endpoints.

Used by the frontend to populate the symbol picker and a "trending tokens"
panel without each component needing to know the full supported-symbol list.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from ..config import settings
from ..database import get_db
import asyncpg
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Symbols"])


@router.get(
    "/symbols",
    summary="List supported symbols",
    description="Returns the configured supported-symbol allowlist with display metadata."
)
async def list_symbols():
    return {
        "symbols": [
            {
                "symbol": sym,
                "name": settings.SYMBOL_METADATA.get(sym, {}).get("name", sym),
                "slug": settings.SYMBOL_METADATA.get(sym, {}).get("slug", sym.lower()),
            }
            for sym in settings.SUPPORTED_SYMBOLS
        ],
        "count": len(settings.SUPPORTED_SYMBOLS),
    }


@router.get(
    "/trending",
    summary="Trending symbols by 24h price change",
    description="Returns supported symbols sorted by 24h price change, derived from v_latest_prices."
)
async def trending_symbols(
    limit: int = Query(10, ge=1, le=50, description="Max rows to return (1-50)"),
    direction: str = Query("abs", regex="^(abs|gainers|losers)$",
                           description="Sort: abs (biggest movers), gainers, or losers"),
    conn: asyncpg.Connection = Depends(get_db),
):
    order_clauses = {
        "abs":      "ABS(price_change_24h) DESC",
        "gainers":  "price_change_24h DESC",
        "losers":   "price_change_24h ASC",
    }
    order_clause = order_clauses[direction]

    sql = f"""
        SELECT
            symbol,
            name,
            price,
            volume_24h,
            market_cap,
            price_change_24h,
            timestamp
        FROM v_latest_prices
        WHERE symbol = ANY($1::text[])
          AND price_change_24h IS NOT NULL
        ORDER BY {order_clause}
        LIMIT $2
    """

    try:
        rows = await conn.fetch(sql, list(settings.SUPPORTED_SYMBOLS), limit)
    except Exception as exc:
        logger.error("Trending query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to compute trending symbols")

    if not rows:
        return {"trending": [], "direction": direction, "count": 0}

    return {
        "direction": direction,
        "count": len(rows),
        "trending": [
            {
                "symbol":            row["symbol"],
                "name":              row["name"],
                "price":             float(row["price"]),
                "volume_24h":        float(row["volume_24h"]) if row["volume_24h"] is not None else None,
                "market_cap":        float(row["market_cap"]) if row["market_cap"] is not None else None,
                "price_change_24h":  float(row["price_change_24h"]),
                "timestamp":         row["timestamp"].isoformat(),
            }
            for row in rows
        ],
    }
