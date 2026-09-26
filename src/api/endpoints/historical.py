"""
Historical price endpoints backed by PostgreSQL / TimescaleDB.

Uses asyncpg natively so queries do not block the ASGI event loop.
Per-request timing is handled by TimingMiddleware, not inline here.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Response, Request
from ..models import HistoricalPriceResponse, ErrorResponse
from ..database import get_db
from ..registry import require_symbol, symbols_of
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import asyncpg
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/historical",
    tags=["Historical Data"]
)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Query params without an offset are treated as UTC; the columns are TIMESTAMPTZ."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


@router.get(
    "/{symbol}",
    response_model=List[HistoricalPriceResponse],
    responses={
        404: {"model": ErrorResponse, "description": "No data found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get historical price data",
    description="Fetches historical 1-minute OHLC candles from PostgreSQL. "
                "Supports date range filtering, ordering, and pagination."
)
async def get_historical_prices(
    request: Request,
    response: Response,
    symbol: str,
    start_time: Optional[datetime] = Query(
        None,
        description="Start time (ISO 8601 format, e.g., 2025-11-16T00:00:00)"
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="End time (ISO 8601 format, e.g., 2025-11-16T23:59:59)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return (1-1000)"),
    offset: int = Query(0, ge=0, description="Records to skip for pagination"),
    order_by: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    conn: asyncpg.Connection = Depends(get_db)
) -> List[HistoricalPriceResponse]:
    symbol = require_symbol(symbols_of(request), symbol)

    end_time = _as_utc(end_time) or datetime.now(timezone.utc)
    start_time = _as_utc(start_time) or end_time - timedelta(hours=24)

    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    if (end_time - start_time).days > 30:
        raise HTTPException(
            status_code=400,
            detail="Time range cannot exceed 30 days. Use smaller ranges with pagination."
        )

    try:
        order_clause = "ASC" if order_by.lower() == "asc" else "DESC"

        sql = f"""
            SELECT
                c.symbol,
                p.window_start,
                p.window_end,
                p.open_price,
                p.high_price,
                p.low_price,
                p.close_price,
                p.vwap,
                p.volume,
                p.quote_volume,
                p.trade_count
            FROM price_aggregates_1m p
            JOIN cryptocurrencies c ON p.crypto_id = c.id
            WHERE c.symbol = $1
                AND p.window_start >= $2
                AND p.window_start <= $3
            ORDER BY p.window_start {order_clause}
            LIMIT $4 OFFSET $5
        """
        rows = await conn.fetch(sql, symbol, start_time, end_time, limit, offset)

        count_sql = """
            SELECT COUNT(*)
            FROM price_aggregates_1m p
            JOIN cryptocurrencies c ON p.crypto_id = c.id
            WHERE c.symbol = $1
                AND p.window_start >= $2
                AND p.window_start <= $3
        """
        total_count = await conn.fetchval(count_sql, symbol, start_time, end_time)

        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Returned-Count"] = str(len(rows))
        response.headers["X-Has-More"] = str(offset + len(rows) < total_count).lower()
        response.headers["X-Cache-Hit"] = "false"

        if not rows:
            logger.warning("No historical data for %s between %s and %s", symbol, start_time, end_time)
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {symbol} in the specified time range"
            )

        results = [
            HistoricalPriceResponse(
                symbol=row["symbol"],
                window_start=row["window_start"],
                window_end=row["window_end"],
                open_price=row["open_price"],
                high_price=row["high_price"],
                low_price=row["low_price"],
                close_price=row["close_price"],
                vwap=row["vwap"],
                volume=row["volume"],
                quote_volume=row["quote_volume"],
                trade_count=row["trade_count"]
            )
            for row in rows
        ]

        logger.info("Retrieved %d/%d historical records for %s", len(results), total_count, symbol)
        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Database error for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@router.get(
    "/{symbol}/stats",
    summary="Get statistical summary",
    description="Returns min, max, avg prices for a given time range"
)
async def get_price_stats(
    request: Request,
    symbol: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    conn: asyncpg.Connection = Depends(get_db)
):
    symbol = require_symbol(symbols_of(request), symbol)

    end_time = _as_utc(end_time) or datetime.now(timezone.utc)
    start_time = _as_utc(start_time) or end_time - timedelta(hours=24)

    try:
        sql = """
            SELECT
                MIN(p.low_price)  AS lowest,
                MAX(p.high_price) AS highest,
                SUM(p.quote_volume) / NULLIF(SUM(p.volume), 0) AS average,       -- VWAP over the range
                SUM(p.quote_volume)                            AS total_volume,  -- USD
                COUNT(*)          AS candle_count
            FROM price_aggregates_1m p
            JOIN cryptocurrencies c ON p.crypto_id = c.id
            WHERE c.symbol = $1
                AND p.window_start >= $2
                AND p.window_start <= $3
        """
        row = await conn.fetchrow(sql, symbol, start_time, end_time)

        if not row or row["lowest"] is None:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        return {
            "symbol": symbol,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "lowest_price": float(row["lowest"]),
            "highest_price": float(row["highest"]),
            "average_price": float(row["average"]),
            "total_volume": float(row["total_volume"]),
            "candle_count": row["candle_count"],
            "price_range": float(row["highest"] - row["lowest"]),
            "price_change_pct": (
                (float(row["highest"]) - float(row["lowest"])) / float(row["lowest"]) * 100
            ) if row["lowest"] else 0
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Stats query error: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to compute statistics: {str(e)}")


@router.get(
    "/{symbol}/latest",
    response_model=HistoricalPriceResponse,
    summary="Get latest historical record",
    description="Fetches the most recent 1-minute candle from PostgreSQL"
)
async def get_latest_historical(
    request: Request,
    symbol: str,
    conn: asyncpg.Connection = Depends(get_db)
) -> HistoricalPriceResponse:
    symbol = require_symbol(symbols_of(request), symbol)

    try:
        sql = """
            SELECT
                c.symbol,
                p.window_start,
                p.window_end,
                p.open_price,
                p.high_price,
                p.low_price,
                p.close_price,
                p.vwap,
                p.volume,
                p.quote_volume,
                p.trade_count
            FROM price_aggregates_1m p
            JOIN cryptocurrencies c ON p.crypto_id = c.id
            WHERE c.symbol = $1
            ORDER BY p.window_start DESC
            LIMIT 1
        """
        row = await conn.fetchrow(sql, symbol)

        if not row:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        return HistoricalPriceResponse(
            symbol=row["symbol"],
            window_start=row["window_start"],
            window_end=row["window_end"],
            open_price=row["open_price"],
            high_price=row["high_price"],
            low_price=row["low_price"],
            close_price=row["close_price"],
            vwap=row["vwap"],
            volume=row["volume"],
            quote_volume=row["quote_volume"],
            trade_count=row["trade_count"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Database error for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
