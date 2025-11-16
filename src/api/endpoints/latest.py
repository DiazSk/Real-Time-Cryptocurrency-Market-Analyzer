"""
Latest Price Endpoint - Fetches from Redis Cache
Phase 4 - Week 8 - Day 1-2

Endpoint: GET /latest/{symbol}
Returns: Latest 1-minute OHLC candle from Redis cache
"""

from fastapi import APIRouter, HTTPException, Depends
from ..models import LatestPriceResponse, ErrorResponse
from ..database import get_redis
import redis
import json
import logging
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/latest",
    tags=["Latest Prices"]
)


@router.get(
    "/{symbol}",
    response_model=LatestPriceResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Symbol not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get latest price for cryptocurrency",
    description="Fetches the most recent 1-minute OHLC candle from Redis cache. "
                "Data is updated in real-time by the Flink streaming pipeline."
)
async def get_latest_price(
    symbol: str,
    redis_client: redis.Redis = Depends(get_redis)
) -> LatestPriceResponse:
    """
    Get latest OHLC data for a cryptocurrency
    
    Args:
        symbol: Cryptocurrency symbol (BTC, ETH)
        redis_client: Redis client instance (injected)
    
    Returns:
        LatestPriceResponse with current OHLC data
    
    Raises:
        HTTPException 404: If symbol not found in cache
        HTTPException 500: If Redis connection fails
    """
    
    # Normalize symbol to uppercase
    symbol = symbol.upper()
    
    # Validate symbol
    if symbol not in ["BTC", "ETH"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol: {symbol}. Supported: BTC, ETH"
        )
    
    # Redis key pattern: crypto:BTC:latest
    redis_key = f"crypto:{symbol}:latest"
    
    try:
        # Fetch from Redis
        cached_data = redis_client.get(redis_key)
        
        if cached_data is None:
            logger.warning(f"No data found in Redis for key: {redis_key}")
            raise HTTPException(
                status_code=404,
                detail=f"No recent data available for {symbol}. "
                       f"Please wait for the next 1-minute window to complete."
            )
        
        # Parse JSON
        data = json.loads(cached_data)
        
        # Convert Unix timestamps (seconds with nanosecond decimals) to datetime
        window_start = datetime.fromtimestamp(data["windowStart"])
        window_end = datetime.fromtimestamp(data["windowEnd"])
        
        # Convert to response model
        response = LatestPriceResponse(
            symbol=data["symbol"],
            window_start=window_start,
            window_end=window_end,
            open=Decimal(str(data["open"])),
            high=Decimal(str(data["high"])),
            low=Decimal(str(data["low"])),
            close=Decimal(str(data["close"])),
            volume_sum=Decimal(str(data["volumeSum"])),
            event_count=data["eventCount"]
        )
        
        logger.info(f"✅ Retrieved latest {symbol} price from Redis")
        return response
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Data format error in cache"
        )
    
    except redis.RedisError as e:
        logger.error(f"Redis error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Cache service unavailable"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
