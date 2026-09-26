"""
Latest-candle endpoints.

Redis holds the newest 1-minute candle per symbol (written by Flink on window close).
On a miss, a corrupt entry, or a Redis outage, the newest row in TimescaleDB is served
instead, so Redis is a cache in front of the database rather than the only source.
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.exceptions import RedisError

from ..database import get_pool, get_redis
from ..models import ErrorResponse, LatestPriceResponse
from ..registry import require_symbol, symbols_of

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/latest", tags=["Latest Prices"])

# One index-backed LIMIT 1 per symbol (PK is crypto_id, window_start).
LATEST_SQL = """
    SELECT c.symbol, p.window_start, p.window_end, p.open_price, p.high_price, p.low_price,
           p.close_price, p.vwap, p.volume, p.quote_volume, p.trade_count
    FROM cryptocurrencies c
    CROSS JOIN LATERAL (
        SELECT * FROM price_aggregates_1m
        WHERE crypto_id = c.id
        ORDER BY window_start DESC
        LIMIT 1
    ) p
    WHERE c.symbol = ANY($1::text[])
"""


def _from_cache(raw: str) -> LatestPriceResponse:
    """Parse the Flink Candle JSON (camelCase keys, window times in epoch seconds).
    parse_float=Decimal keeps Java BigDecimal prices exact."""
    d = json.loads(raw, parse_float=Decimal)
    return LatestPriceResponse(
        symbol=d["symbol"],
        window_start=datetime.fromtimestamp(float(d["windowStart"]), tz=timezone.utc),
        window_end=datetime.fromtimestamp(float(d["windowEnd"]), tz=timezone.utc),
        open=d["open"], high=d["high"], low=d["low"], close=d["close"],
        vwap=d["vwap"], volume=d["volume"], quote_volume=d["quoteVolume"], trade_count=d["tradeCount"],
    )


def _from_row(row) -> LatestPriceResponse:
    return LatestPriceResponse(
        symbol=row["symbol"], window_start=row["window_start"], window_end=row["window_end"],
        open=row["open_price"], high=row["high_price"], low=row["low_price"], close=row["close_price"],
        vwap=row["vwap"], volume=row["volume"], quote_volume=row["quote_volume"], trade_count=row["trade_count"],
    )


async def _latest(symbols: list[str], redis_client, pool) -> tuple[dict, dict]:
    """Newest candle per symbol: Redis first, one PostgreSQL query for all misses.
    Returns (candles by symbol, source by symbol)."""
    candles, sources = {}, {}
    for sym in symbols:
        try:
            raw = await redis_client.get(f"crypto:{sym}:latest")
            if raw is not None:
                candles[sym], sources[sym] = _from_cache(raw), "redis"
        except RedisError as e:
            logger.warning("Redis unavailable for %s, falling back to PostgreSQL: %s", sym, e)
        except (ValueError, KeyError) as e:
            logger.warning("Corrupt cache entry for %s, falling back to PostgreSQL: %s", sym, e)

    misses = [s for s in symbols if s not in candles]
    if misses:
        for row in await pool.fetch(LATEST_SQL, misses):
            candles[row["symbol"]], sources[row["symbol"]] = _from_row(row), "postgres"
    return candles, sources


@router.get("/all", summary="Latest candle for every tracked symbol")
async def get_all_latest_prices(
    request: Request,
    response: Response,
    redis_client=Depends(get_redis),
    pool=Depends(get_pool),
):
    symbols = list(symbols_of(request))
    candles, sources = await _latest(symbols, redis_client, pool)
    hits = sum(1 for s in sources.values() if s == "redis")
    hit_rate = f"{hits / len(symbols) * 100:.1f}%"
    response.headers["X-Total-Symbols"] = str(len(symbols))
    response.headers["X-Cache-Hits"] = str(hits)
    response.headers["X-Cache-Hit-Rate"] = hit_rate

    if not candles:
        raise HTTPException(status_code=404, detail="No candles yet for any symbol")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prices": {sym: c.model_dump(mode="json") for sym, c in candles.items()},
        "cache_hit_rate": hit_rate,
    }


@router.get(
    "/{symbol}",
    response_model=LatestPriceResponse,
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
    summary="Latest candle for one symbol",
)
async def get_latest_price(
    symbol: str,
    request: Request,
    response: Response,
    redis_client=Depends(get_redis),
    pool=Depends(get_pool),
) -> LatestPriceResponse:
    symbol = require_symbol(symbols_of(request), symbol)
    candles, sources = await _latest([symbol], redis_client, pool)
    if symbol not in candles:
        raise HTTPException(
            status_code=404,
            detail=f"No candle for {symbol} yet; the first one appears after the first full minute of trades.",
        )
    candle = candles[symbol]
    response.headers["X-Data-Source"] = sources[symbol]
    response.headers["X-Cache-Hit"] = str(sources[symbol] == "redis").lower()
    response.headers["X-Data-Age-Seconds"] = str(
        int((datetime.now(timezone.utc) - candle.window_end).total_seconds())
    )
    return candle
