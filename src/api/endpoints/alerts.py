"""
Alerts Endpoint - Fetches Recent Price Anomalies
Phase 4 - Week 9 - Day 5-7

Endpoint: GET /api/v1/alerts/{symbol}
Returns: Recent price anomaly alerts from Kafka topic
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Response
from ..database import get_postgres_connection
from typing import List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"]
)


class AlertResponse:
    """Alert response model"""
    def __init__(self, data: dict):
        self.symbol = data[0]
        self.alert_type = data[1]
        self.price_change_pct = float(data[2])
        self.old_price = float(data[3])
        self.new_price = float(data[4])
        self.window_start = data[5]
        self.window_end = data[6]
        self.created_at = data[7]


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
    conn=Depends(get_postgres_connection)
):
    """
    Get recent price anomaly alerts
    
    Args:
        symbol: Cryptocurrency symbol (BTC, ETH, or 'all' for both)
        limit: Maximum number of alerts
        hours: Hours to look back (default 24, max 168=1 week)
        conn: PostgreSQL connection
    
    Returns:
        List of recent alerts
    """
    
    symbol = symbol.upper()
    
    try:
        cursor = conn.cursor()
        
        # Build query based on symbol
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
                WHERE pa.created_at >= NOW() - INTERVAL '%s hours'
                ORDER BY pa.created_at DESC
                LIMIT %s
            """
            cursor.execute(sql, (hours, limit))
        else:
            # Validate symbol
            if symbol not in ["BTC", "ETH"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid symbol: {symbol}. Supported: BTC, ETH, ALL"
                )
            
            crypto_id_map = {"BTC": 1, "ETH": 2}
            crypto_id = crypto_id_map[symbol]
            
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
                WHERE pa.crypto_id = %s
                    AND pa.created_at >= NOW() - INTERVAL '%s hours'
                ORDER BY pa.created_at DESC
                LIMIT %s
            """
            cursor.execute(sql, (crypto_id, hours, limit))
        
        rows = cursor.fetchall()
        cursor.close()
        
        # Convert to response format
        alerts = []
        for row in rows:
            alerts.append({
                "symbol": row[0],
                "alert_type": row[1],
                "price_change_pct": float(row[2]),
                "old_price": float(row[3]),
                "new_price": float(row[4]),
                "window_start": row[5].isoformat() if row[5] else None,
                "window_end": row[6].isoformat() if row[6] else None,
                "created_at": row[7].isoformat() if row[7] else None
            })
        
        # Add metadata headers
        response.headers["X-Total-Alerts"] = str(len(alerts))
        response.headers["X-Lookback-Hours"] = str(hours)
        
        logger.info(f"✅ Retrieved {len(alerts)} alerts for {symbol}")
        
        return {
            "symbol": symbol,
            "alert_count": len(alerts),
            "lookback_hours": hours,
            "alerts": alerts
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
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
    limit: int = Query(20, ge=1, le=100),
    hours: int = Query(24, ge=1, le=168),
    conn=Depends(get_postgres_connection)
):
    """Get all recent alerts (same as /alerts/all)"""
    return await get_alerts(Response(), "ALL", limit, hours, conn)
