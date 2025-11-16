"""
Latest Price Endpoint - Fetches from Redis Cache
Phase 4 - Week 8 - Day 3: Enhanced with performance metrics

Endpoint: GET /latest/{symbol}
Returns: Latest 1-minute OHLC candle from Redis cache
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from ..models import LatestPriceResponse, ErrorResponse
from ..database import get_redis
import redis
import json
import logging
from datetime import datetime
from decimal import Decimal
import time

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/latest",
    tags=["Latest Prices"]
)


@router.get(
    "/all",
    summary="Get all latest prices",
    description="Fetches latest prices for all supported cryptocurrencies"
)
async def get_all_latest_prices(
    response: Response,
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Get latest prices for all cryptocurrencies
    
    Returns a dictionary with BTC and ETH latest prices.
    """
    
    start_perf = time.time()
    
    symbols = ["BTC", "ETH"]
    results = {}
    cache_hits = 0
    
    try:
        for symbol in symbols:
            redis_key = f"crypto:{symbol}:latest"
            cached_data = redis_client.get(redis_key)
            
            if cached_data:
                data = json.loads(cached_data)
                results[symbol] = {
                    "symbol": data["symbol"],
                    "window_start": datetime.fromtimestamp(data["windowStart"]).isoformat(),
                    "window_end": datetime.fromtimestamp(data["windowEnd"]).isoformat(),
                    "open": data["open"],
                    "high": data["high"],
                    "low": data["low"],
                    "close": data["close"],
                    "volume_sum": data["volumeSum"],
                    "event_count": data["eventCount"]
                }
                cache_hits += 1
        
        query_time_ms = (time.time() - start_perf) * 1000
        
        # Add performance headers
        response.headers["X-Total-Symbols"] = str(len(symbols))
        response.headers["X-Cache-Hits"] = str(cache_hits)
        response.headers["X-Cache-Hit-Rate"] = f"{(cache_hits / len(symbols)) * 100:.1f}%"
        response.headers["X-Query-Time-Ms"] = f"{query_time_ms:.2f}"
        
        if not results:
            raise HTTPException(
                status_code=404,
                detail="No data available for any cryptocurrency"
            )
        
        logger.info(f"✅ Retrieved {cache_hits}/{len(symbols)} latest prices ({query_time_ms:.2f}ms)")
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "prices": results,
            "cache_hit_rate": f"{(cache_hits / len(symbols)) * 100:.1f}%"
        }
        
    except Exception as e:
        logger.error(f"Error fetching all prices: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch prices: {str(e)}"
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
                "Data is updated in real-time by the Flink streaming pipeline. "
                "Includes cache hit metrics and query performance in response headers."
)
async def get_latest_price(
    response: Response,
    symbol: str,
    redis_client: redis.Redis = Depends(get_redis)
) -> LatestPriceResponse:
    """
    Get latest OHLC data for a cryptocurrency
    
    Args:
        response: FastAPI response object for headers (injected)
        symbol: Cryptocurrency symbol (BTC, ETH)
        redis_client: Redis client instance (injected)
    
    Returns:
        LatestPriceResponse with current OHLC data
    
    Raises:
        HTTPException 404: If symbol not found in cache
        HTTPException 500: If Redis connection fails
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
    
    # Redis key pattern: crypto:BTC:latest
    redis_key = f"crypto:{symbol}:latest"
    
    try:
        # Fetch from Redis
        cached_data = redis_client.get(redis_key)
        
        # Calculate cache lookup time
        query_time_ms = (time.time() - start_perf) * 1000
        
        if cached_data is None:
            # Add headers even for cache miss
            response.headers["X-Cache-Hit"] = "false"
            response.headers["X-Query-Time-Ms"] = f"{query_time_ms:.2f}"
            
            logger.warning(f"Cache miss for key: {redis_key}")
            raise HTTPException(
                status_code=404,
                detail=f"No recent data available for {symbol}. "
                       f"Please wait for the next 1-minute window to complete."
            )
        
        # Parse JSON
        data = json.loads(cached_data)
        
        # Get TTL (time to live) for the key
        ttl = redis_client.ttl(redis_key)
        
        # Convert to response model
        result = LatestPriceResponse(
            symbol=data["symbol"],
            window_start=datetime.fromtimestamp(data["windowStart"]),
            window_end=datetime.fromtimestamp(data["windowEnd"]),
            open=Decimal(str(data["open"])),
            high=Decimal(str(data["high"])),
            low=Decimal(str(data["low"])),
            close=Decimal(str(data["close"])),
            volume_sum=Decimal(str(data["volumeSum"])),
            event_count=data["eventCount"]
        )
        
        # Add performance and cache headers
        response.headers["X-Cache-Hit"] = "true"
        response.headers["X-Query-Time-Ms"] = f"{query_time_ms:.2f}"
        response.headers["X-Cache-TTL-Seconds"] = str(ttl)
        response.headers["X-Data-Source"] = "redis"
        response.headers["X-Data-Age-Seconds"] = str(
            int((datetime.utcnow() - result.window_end).total_seconds())
        )
        
        logger.info(f"✅ Cache hit for {symbol} (query: {query_time_ms:.2f}ms, TTL: {ttl}s)")
        return result
        
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
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
