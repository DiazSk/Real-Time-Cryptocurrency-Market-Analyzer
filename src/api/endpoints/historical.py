"""
Historical Price Endpoint - Fetches from PostgreSQL
Phase 4 - Week 8 - Day 3: Enhanced with query parameters and performance metrics

Endpoint: GET /historical/{symbol}
Returns: Historical 1-minute OHLC candles from PostgreSQL with advanced filtering
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Response
from ..models import HistoricalPriceResponse, ErrorResponse
from ..database import get_postgres_connection
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/historical",
    tags=["Historical Data"]
)


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
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of records to return (1-1000)"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of records to skip for pagination"
    ),
    order_by: str = Query(
        "desc",
        regex="^(asc|desc)$",
        description="Sort order: 'asc' (oldest first) or 'desc' (newest first)"
    ),
    conn=Depends(get_postgres_connection)
) -> List[HistoricalPriceResponse]:
    """
    Get historical OHLC data for a cryptocurrency
    
    Args:
        response: FastAPI response object for headers (injected)
        symbol: Cryptocurrency symbol (BTC, ETH)
        start_time: Optional start time filter
        end_time: Optional end time filter
        limit: Maximum records to return (default 100, max 1000)
        offset: Records to skip for pagination (default 0)
        order_by: Sort order - 'asc' or 'desc' (default desc)
        conn: PostgreSQL connection (injected)
    
    Returns:
        List of HistoricalPriceResponse objects
    
    Raises:
        HTTPException 400: Invalid parameters
        HTTPException 404: If no data found
        HTTPException 500: If database query fails
    """
    
    # Start performance timer
    start_perf = time.time()
    
    # Normalize symbol to uppercase
    symbol = symbol.upper()
    
    # Validate symbol
    if symbol not in ["BTC", "ETH"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol: {symbol}. Supported: BTC, ETH"
        )
    
    # Map symbol to crypto_id
    crypto_id_map = {"BTC": 1, "ETH": 2}
    crypto_id = crypto_id_map[symbol]
    
    # Default time range: last 24 hours
    if end_time is None:
        end_time = datetime.utcnow()
    if start_time is None:
        start_time = end_time - timedelta(hours=24)
    
    # Validate time range
    if start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="start_time must be before end_time"
        )
    
    # Check if time range is too large (more than 30 days)
    time_diff = end_time - start_time
    if time_diff.days > 30:
        raise HTTPException(
            status_code=400,
            detail="Time range cannot exceed 30 days. Please use smaller date ranges with pagination."
        )
    
    try:
        cursor = conn.cursor()
        
        # Build SQL query with dynamic ordering
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
                p.avg_price,
                p.volume_sum,
                p.trade_count
            FROM price_aggregates_1m p
            JOIN cryptocurrencies c ON p.crypto_id = c.id
            WHERE p.crypto_id = %s
                AND p.window_start >= %s
                AND p.window_start <= %s
            ORDER BY p.window_start {order_clause}
            LIMIT %s OFFSET %s
        """
        
        # Execute query
        cursor.execute(sql, (crypto_id, start_time, end_time, limit, offset))
        rows = cursor.fetchall()
        
        # Get total count for pagination metadata
        count_sql = """
            SELECT COUNT(*) 
            FROM price_aggregates_1m 
            WHERE crypto_id = %s 
                AND window_start >= %s 
                AND window_start <= %s
        """
        cursor.execute(count_sql, (crypto_id, start_time, end_time))
        total_count = cursor.fetchone()[0]
        
        cursor.close()
        
        # Calculate performance metrics
        query_time_ms = (time.time() - start_perf) * 1000
        
        # Add custom response headers
        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Returned-Count"] = str(len(rows))
        response.headers["X-Query-Time-Ms"] = f"{query_time_ms:.2f}"
        response.headers["X-Has-More"] = str(offset + len(rows) < total_count).lower()
        response.headers["X-Cache-Hit"] = "false"  # PostgreSQL always queries DB
        
        # Check if any data found
        if not rows:
            logger.warning(f"No historical data found for {symbol} between {start_time} and {end_time}")
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {symbol} in the specified time range"
            )
        
        # Convert to response models
        results = []
        for row in rows:
            results.append(HistoricalPriceResponse(
                symbol=row[0],
                window_start=row[1],
                window_end=row[2],
                open_price=row[3],
                high_price=row[4],
                low_price=row[5],
                close_price=row[6],
                avg_price=row[7],
                volume_sum=row[8],
                trade_count=row[9]
            ))
        
        logger.info(f"✅ Retrieved {len(results)}/{total_count} historical records for {symbol} "
                   f"(query: {query_time_ms:.2f}ms)")
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}"
        )


@router.get(
    "/{symbol}/stats",
    summary="Get statistical summary",
    description="Returns min, max, avg prices for a given time range"
)
async def get_price_stats(
    symbol: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    conn=Depends(get_postgres_connection)
):
    """
    Get statistical summary of price data
    
    Returns min, max, average prices and total volume for the time range.
    """
    
    symbol = symbol.upper()
    
    if symbol not in ["BTC", "ETH"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol: {symbol}. Supported: BTC, ETH"
        )
    
    crypto_id_map = {"BTC": 1, "ETH": 2}
    crypto_id = crypto_id_map[symbol]
    
    # Default time range: last 24 hours
    if end_time is None:
        end_time = datetime.utcnow()
    if start_time is None:
        start_time = end_time - timedelta(hours=24)
    
    try:
        cursor = conn.cursor()
        
        sql = """
            SELECT 
                MIN(low_price) as lowest,
                MAX(high_price) as highest,
                AVG(avg_price) as average,
                SUM(volume_sum) as total_volume,
                COUNT(*) as candle_count
            FROM price_aggregates_1m
            WHERE crypto_id = %s
                AND window_start >= %s
                AND window_start <= %s
        """
        
        cursor.execute(sql, (crypto_id, start_time, end_time))
        row = cursor.fetchone()
        cursor.close()
        
        if not row or row[0] is None:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol}"
            )
        
        return {
            "symbol": symbol,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "lowest_price": float(row[0]),
            "highest_price": float(row[1]),
            "average_price": float(row[2]),
            "total_volume": float(row[3]),
            "candle_count": row[4],
            "price_range": float(row[1] - row[0]),
            "price_change_pct": ((float(row[1]) - float(row[0])) / float(row[0]) * 100) if row[0] else 0
        }
        
    except Exception as e:
        logger.error(f"Stats query error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute statistics: {str(e)}"
        )


@router.get(
    "/{symbol}/latest",
    response_model=HistoricalPriceResponse,
    summary="Get latest historical record",
    description="Fetches the most recent 1-minute candle from PostgreSQL"
)
async def get_latest_historical(
    symbol: str,
    conn=Depends(get_postgres_connection)
) -> HistoricalPriceResponse:
    """
    Get most recent historical record for a cryptocurrency
    
    This is useful for comparing Redis cache vs PostgreSQL data.
    """
    
    # Normalize symbol
    symbol = symbol.upper()
    
    # Validate symbol
    if symbol not in ["BTC", "ETH"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol: {symbol}. Supported: BTC, ETH"
        )
    
    # Map symbol to crypto_id
    crypto_id_map = {"BTC": 1, "ETH": 2}
    crypto_id = crypto_id_map[symbol]
    
    try:
        cursor = conn.cursor()
        
        sql = """
            SELECT 
                c.symbol,
                p.window_start,
                p.window_end,
                p.open_price,
                p.high_price,
                p.low_price,
                p.close_price,
                p.avg_price,
                p.volume_sum,
                p.trade_count
            FROM price_aggregates_1m p
            JOIN cryptocurrencies c ON p.crypto_id = c.id
            WHERE p.crypto_id = %s
            ORDER BY p.window_start DESC
            LIMIT 1
        """
        
        cursor.execute(sql, (crypto_id,))
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol}"
            )
        
        return HistoricalPriceResponse(
            symbol=row[0],
            window_start=row[1],
            window_end=row[2],
            open_price=row[3],
            high_price=row[4],
            low_price=row[5],
            close_price=row[6],
            avg_price=row[7],
            volume_sum=row[8],
            trade_count=row[9]
        )
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}"
        )
