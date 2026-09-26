"""
Alerts Endpoint - Fetches Recent Price Anomalies

Endpoint: GET /api/v1/alerts/{symbol}
Returns: Recent price anomaly alerts from PostgreSQL
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Response, Request
from ..database import get_db
from ..registry import require_symbol, symbols_of
from datetime import datetime, timedelta, timezone
import asyncpg
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"]
)


ALERTS_SQL = """
    SELECT c.symbol, pa.alert_type, pa.severity, pa.z_score, pa.price_change_pct,
           pa.old_price, pa.new_price, pa.window_start, pa.window_end, pa.created_at
    FROM price_alerts pa
    JOIN cryptocurrencies c ON pa.crypto_id = c.id
    WHERE ($1::text IS NULL OR c.symbol = $1)
      AND pa.created_at >= $2
    ORDER BY pa.created_at DESC
    LIMIT $3
"""


def _serialize_alert(row) -> dict:
    return {
        "symbol": row["symbol"],
        "alert_type": row["alert_type"],
        "severity": row["severity"],
        "z_score": float(row["z_score"]),
        "price_change_pct": float(row["price_change_pct"]),
        "old_price": float(row["old_price"]),
        "new_price": float(row["new_price"]),
        "window_start": row["window_start"].isoformat(),
        "window_end": row["window_end"].isoformat(),
        "created_at": row["created_at"].isoformat(),
    }


@router.get(
    "/{symbol}",
    summary="Get recent price alerts",
    description="Fetches recent anomaly detection alerts for a cryptocurrency"
)
async def get_alerts(
    request: Request,
    response: Response,
    symbol: str,
    limit: int = Query(10, ge=1, le=100, description="Maximum alerts to return"),
    hours: int = Query(24, ge=1, le=168, description="Look back period in hours"),
    conn: asyncpg.Connection = Depends(get_db)
):
    symbol = require_symbol(symbols_of(request), symbol, allow_all=True)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = await conn.fetch(ALERTS_SQL, None if symbol == "ALL" else symbol, cutoff, limit)
    alerts = [_serialize_alert(row) for row in rows]

    response.headers["X-Total-Alerts"] = str(len(alerts))
    response.headers["X-Lookback-Hours"] = str(hours)
    return {"symbol": symbol, "alert_count": len(alerts), "lookback_hours": hours, "alerts": alerts}


@router.get(
    "/",
    summary="Get all recent alerts",
    description="Fetches recent alerts for all cryptocurrencies"
)
async def get_all_alerts(
    request: Request,
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    hours: int = Query(24, ge=1, le=168),
    conn: asyncpg.Connection = Depends(get_db)
):
    return await get_alerts(request, response, "ALL", limit, hours, conn)
