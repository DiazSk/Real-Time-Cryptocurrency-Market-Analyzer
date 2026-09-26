"""
Pydantic Models for API Request/Response Validation
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
    """Most recent completed 1-minute candle. X-Data-Source says whether Redis or PostgreSQL served it."""
    symbol: str
    window_start: datetime
    window_end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    vwap: Decimal = Field(..., description="Volume-weighted average price")
    volume: Decimal = Field(..., description="Base-asset units traded")
    quote_volume: Decimal = Field(..., description="USD traded (sum of price * size)")
    trade_count: int = Field(..., description="Number of trades in the window")


class HistoricalPriceResponse(BaseModel):
    """One persisted 1-minute candle from price_aggregates_1m."""
    symbol: str
    window_start: datetime
    window_end: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    vwap: Decimal
    volume: Decimal
    quote_volume: Decimal
    trade_count: int


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
