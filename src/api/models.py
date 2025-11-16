"""
Pydantic Models for API Request/Response Validation
Phase 4 - Week 8
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    services: dict


class LatestPriceResponse(BaseModel):
    """
    Response model for /latest/{symbol} endpoint
    """
    symbol: str = Field(..., description="Cryptocurrency symbol (BTC, ETH)")
    window_start: datetime = Field(..., description="Window start time")
    window_end: datetime = Field(..., description="Window end time")
    open: Decimal = Field(..., description="Opening price")
    high: Decimal = Field(..., description="Highest price")
    low: Decimal = Field(..., description="Lowest price")
    close: Decimal = Field(..., description="Closing price")
    volume_sum: Decimal = Field(..., description="Total volume")
    event_count: int = Field(..., description="Number of price updates")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTC",
                "window_start": "2025-11-16T05:30:00Z",
                "window_end": "2025-11-16T05:31:00Z",
                "open": 95750.00,
                "high": 95800.00,
                "low": 95700.00,
                "close": 95780.00,
                "volume_sum": 78701577213.28,
                "event_count": 12
            }
        }


class HistoricalPriceResponse(BaseModel):
    """
    Response model for /historical/{symbol} endpoint
    """
    symbol: str
    window_start: datetime
    window_end: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    avg_price: Decimal
    volume_sum: Decimal
    trade_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTC",
                "window_start": "2025-11-16T05:30:00Z",
                "window_end": "2025-11-16T05:31:00Z",
                "open_price": 95750.00,
                "high_price": 95800.00,
                "low_price": 95700.00,
                "close_price": 95780.00,
                "avg_price": 95757.50,
                "volume_sum": 78701577213.28,
                "trade_count": 12
            }
        }


class HistoricalDataQuery(BaseModel):
    """
    Query parameters for historical data
    """
    start_time: Optional[datetime] = Field(None, description="Start time (ISO format)")
    end_time: Optional[datetime] = Field(None, description="End time (ISO format)")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of records")


class ErrorResponse(BaseModel):
    """
    Standard error response
    """
    error: str
    detail: Optional[str] = None
    timestamp: datetime


class WebSocketMessage(BaseModel):
    """
    WebSocket message format
    """
    type: str = Field(..., description="Message type: 'price_update', 'error', 'connection'")
    data: dict = Field(..., description="Message payload")
    timestamp: datetime
