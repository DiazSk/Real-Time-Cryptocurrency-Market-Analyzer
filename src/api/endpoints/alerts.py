"""
Alerts Endpoint - Fetches Recent Price Anomalies

Endpoint: GET /api/v1/alerts/{symbol}
Returns: Recent price anomaly alerts from PostgreSQL
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Response
from ..database import get_db
from ..config import settings
from datetime import datetime, timedelta
import asyncpg
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"]
)


def _serialize_alert(row) -> dict:
    return {
        "symbol": row["symbol"],
        "alert_type": row["alert_type"],
        "price_change_pct": float(row["price_change_pct"]),
        "old_price": float(row["old_price"]),
        "new_price": float(row["new_price"]),
        "window_start": row["window_start"].isoformat() if row["window_start"] else None,
        "window_end": row["window_end"].isoformat() if row["window_end"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get(
    "/{symbol}",
    summary="Get recent price alerts",
    description="Fetches recent anomaly detection alerts for a cryptocurrency"
)
async def get_alerts(
    response: Response,
    symbol: str,
    limit: int = Query(10, ge=1, le=100, description="Maximum alerts to return"),
    hours: int = Query(24, ge=1, le=168, description="Look back period in hours"),
    conn: asyncpg.Connection = Depends(get_db)
):
    symbol = symbol.upper()
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    try:
        if symbol == "ALL":
            sql = """
                SELECT
                    c.symbol,
                    pa.alert_type,
                    pa.price_change_pct,
                    pa.old_price,
                    pa.new_price,
                    pa.window_start,
                    pa.window_end,
                    pa.created_at
                FROM price_alerts pa
                JOIN cryptocurrencies c ON pa.crypto_id = c.id
                WHERE pa.created_at >= $1
                ORDER BY pa.created_at DESC
                LIMIT $2
            """
            rows = await conn.fetch(sql, cutoff, limit)
        else:
            if symbol not in settings.SUPPORTED_SYMBOLS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid symbol: {symbol}. Supported: {', '.join(settings.SUPPORTED_SYMBOLS)}, ALL"
                )

            sql = """
                SELECT
                    c.symbol,
                    pa.alert_type,
                    pa.price_change_pct,
                    pa.old_price,
                    pa.new_price,
                    pa.window_start,
                    pa.window_end,
                    pa.created_at
                FROM price_alerts pa
                JOIN cryptocurrencies c ON pa.crypto_id = c.id
                WHERE c.symbol = $1
                    AND pa.created_at >= $2
                ORDER BY pa.created_at DESC
                LIMIT $3
            """
            rows = await conn.fetch(sql, symbol, cutoff, limit)

        alerts = [_serialize_alert(row) for row in rows]

        response.headers["X-Total-Alerts"] = str(len(alerts))
        response.headers["X-Lookback-Hours"] = str(hours)

        logger.info("Retrieved %d alerts for %s", len(alerts), symbol)

        return {
            "symbol": symbol,
            "alert_count": len(alerts),
            "lookback_hours": hours,
            "alerts": alerts,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching alerts: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch alerts: {str(e)}"
        )


@router.get(
    "/",
    summary="Get all recent alerts",
    description="Fetches recent alerts for all cryptocurrencies"
)
async def get_all_alerts(
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    hours: int = Query(24, ge=1, le=168),
    conn: asyncpg.Connection = Depends(get_db)
):
    return await get_alerts(response, "ALL", limit, hours, conn)
