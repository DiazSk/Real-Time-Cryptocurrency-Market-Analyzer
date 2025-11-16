"""
Historical Price Endpoint - Fetches from PostgreSQL
Phase 4 - Week 8 - Day 1-2

Endpoint: GET /historical/{symbol}
Returns: Historical 1-minute OHLC candles from PostgreSQL
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from ..models import HistoricalPriceResponse, ErrorResponse
from ..database import get_postgres_connection
from typing import List, Optional
from datetime import datetime, timedelta
import logging

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
                "Supports date range filtering and pagination."
)
async def get_historical_prices(
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
    conn=Depends(get_postgres_connection)
) -> List[HistoricalPriceResponse]:
    """
    Get historical OHLC data for a cryptocurrency
    
    Args:
        symbol: Cryptocurrency symbol (BTC, ETH)
        start_time: Optional start time filter
        end_time: Optional end time filter
        limit: Maximum records to return (default 100, max 1000)
        conn: PostgreSQL connection (injected)
    
    Returns:
        List of HistoricalPriceResponse objects
    
    Raises:
        HTTPException 404: If no data found
        HTTPException 500: If database query fails
    """
    
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
    
    try:
        cursor = conn.cursor()
        
        # Build SQL query
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
                AND p.window_start >= %s
                AND p.window_start <= %s
            ORDER BY p.window_start DESC
            LIMIT %s
        """
        
        # Execute query
        cursor.execute(sql, (crypto_id, start_time, end_time, limit))
        rows = cursor.fetchall()
        
        cursor.close()
        
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
        
        logger.info(f"✅ Retrieved {len(results)} historical records for {symbol}")
        return results
        
    except Exception as e:
        logger.error(f"Database error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}"
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
