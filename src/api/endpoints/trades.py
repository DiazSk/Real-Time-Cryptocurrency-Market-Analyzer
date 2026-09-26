"""
Recent raw trades for one symbol.

Seeds the frontend's live trade line so it opens with the last N seconds of
Coinbase trades (as stored by the Flink raw_trades sink) instead of an empty
window. The WebSocket `trade` frames carry it forward from there.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query, Request

from ..database import get_db
from ..registry import require_symbol, symbols_of

router = APIRouter(tags=["Trades"])


@router.get(
    "/trades/{symbol}",
    summary="Recent trades",
    description="(time, price) for the symbol's trades in the last `seconds` (max 300), oldest first. "
                "`time` is epoch seconds, matching the WebSocket `trade` frame.",
)
async def recent_trades(
    request: Request,
    symbol: str,
    seconds: int = Query(60, ge=1, le=300, description="Look-back window in seconds (1-300)"),
    conn: asyncpg.Connection = Depends(get_db),
):
    symbol = require_symbol(symbols_of(request), symbol)
    rows = await conn.fetch(
        """
        SELECT EXTRACT(EPOCH FROM t.event_time)::float8 AS time, t.price::float8 AS price
        FROM raw_trades t
        JOIN cryptocurrencies c ON t.crypto_id = c.id
        WHERE c.symbol = $1
          AND t.event_time >= now() - make_interval(secs => $2)
        ORDER BY t.event_time ASC
        LIMIT 5000
        """,
        symbol,
        seconds,
    )
    return {
        "symbol": symbol,
        "seconds": seconds,
        "trades": [{"time": float(r["time"]), "price": float(r["price"])} for r in rows],
    }
