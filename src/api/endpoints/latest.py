"""
Latest price endpoints backed by Redis cache.

All Redis I/O uses the async client so the ASGI event loop is never blocked.
Per-request timing is handled by TimingMiddleware in middleware.py, not inline here.
"""

from fastapi import APIRouter, HTTPException, Depends, Response, Request
from ..models import LatestPriceResponse, ErrorResponse
from ..database import get_redis
import redis.asyncio as aioredis
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
    "/all",
    summary="Get all latest prices",
    description="Fetches latest prices for all supported cryptocurrencies"
)
async def get_all_latest_prices(
    response: Response,
    redis_client: aioredis.Redis = Depends(get_redis)
):
    symbols = ["BTC", "ETH"]
    results = {}
    cache_hits = 0

    try:
        for symbol in symbols:
            redis_key = f"crypto:{symbol}:latest"
            cached_data = await redis_client.get(redis_key)

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

        response.headers["X-Total-Symbols"] = str(len(symbols))
        response.headers["X-Cache-Hits"] = str(cache_hits)
        response.headers["X-Cache-Hit-Rate"] = f"{(cache_hits / len(symbols)) * 100:.1f}%"

        if not results:
            raise HTTPException(
                status_code=404,
                detail="No data available for any cryptocurrency"
            )

        logger.info("Retrieved %d/%d latest prices", cache_hits, len(symbols))

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "prices": results,
            "cache_hit_rate": f"{(cache_hits / len(symbols)) * 100:.1f}%"
        }

    except Exception as e:
        logger.error("Error fetching all prices: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch prices: {str(e)}")


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
    response: Response,
    symbol: str,
    redis_client: aioredis.Redis = Depends(get_redis)
) -> LatestPriceResponse:
    symbol = symbol.upper()

    if symbol not in ["BTC", "ETH"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol: {symbol}. Supported: BTC, ETH"
        )

    redis_key = f"crypto:{symbol}:latest"

    try:
        cached_data = await redis_client.get(redis_key)

        if cached_data is None:
            response.headers["X-Cache-Hit"] = "false"
            logger.warning("Cache miss for key: %s", redis_key)
            raise HTTPException(
                status_code=404,
                detail=f"No recent data available for {symbol}. "
                       f"Please wait for the next 1-minute window to complete."
            )

        data = json.loads(cached_data)
        ttl = await redis_client.ttl(redis_key)

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

        response.headers["X-Cache-Hit"] = "true"
        response.headers["X-Cache-TTL-Seconds"] = str(ttl)
        response.headers["X-Data-Source"] = "redis"
        response.headers["X-Data-Age-Seconds"] = str(
            int((datetime.utcnow() - result.window_end).total_seconds())
        )

        logger.info("Cache hit for %s (TTL: %ss)", symbol, ttl)
        return result

    except json.JSONDecodeError as e:
        logger.error("JSON decode error for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Data format error in cache")

    except aioredis.RedisError as e:
        logger.error("Redis error for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Cache service unavailable")

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Unexpected error for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
