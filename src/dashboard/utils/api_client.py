"""
API Client for FastAPI Backend
Phase 4 - Week 9 - Day 1-2

Handles all communication with the FastAPI backend.
"""

import requests
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import time
import sys
from pathlib import Path

# Add dashboard directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_BASE_URL, API_TIMEOUT, MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


class CryptoAPIClient:
    """
    Client for communicating with the Crypto Market Analyzer API
    """
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = API_TIMEOUT
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """
        Make HTTP request with retry logic
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional request arguments
            
        Returns:
            Response JSON or None if failed
        """
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"All retry attempts failed for {url}")
                    return None
        
        return None
    
    def get_health(self) -> Optional[Dict]:
        """
        Check API health status
        
        Returns:
            Health check response or None
        """
        return self._make_request("GET", "/health")
    
    def get_latest_price(self, symbol: str) -> Optional[Dict]:
        """
        Get latest price for a cryptocurrency
        
        Args:
            symbol: Cryptocurrency symbol (BTC, ETH)
            
        Returns:
            Latest price data or None
        """
        return self._make_request("GET", f"/api/v1/latest/{symbol}")
    
    def get_all_latest_prices(self) -> Optional[Dict]:
        """
        Get latest prices for all cryptocurrencies
        
        Returns:
            Dictionary with all latest prices or None
        """
        return self._make_request("GET", "/api/v1/latest/all")
    
    def get_historical_data(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "desc"
    ) -> Optional[List[Dict]]:
        """
        Get historical price data
        
        Args:
            symbol: Cryptocurrency symbol (BTC, ETH)
            start_time: Start of time range
            end_time: End of time range  
            limit: Maximum records to return
            offset: Number of records to skip
            order_by: Sort order (asc or desc)
            
        Returns:
            List of historical price records or None
        """
        params = {
            "limit": limit,
            "offset": offset,
            "order_by": order_by
        }
        
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        
        return self._make_request("GET", f"/api/v1/historical/{symbol}", params=params)
    
    def get_statistics(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Optional[Dict]:
        """
        Get statistical summary for a cryptocurrency
        
        Args:
            symbol: Cryptocurrency symbol (BTC, ETH)
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            Statistics dictionary or None
        """
        params = {}
        
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        
        return self._make_request("GET", f"/api/v1/historical/{symbol}/stats", params=params)
    
    def get_alerts(self, symbol: str = "ALL", limit: int = 10, hours: int = 24) -> Optional[Dict]:
        """
        Get recent price anomaly alerts
        
        Args:
            symbol: Cryptocurrency symbol (BTC, ETH, or ALL)
            limit: Maximum alerts to return
            hours: Hours to look back
            
        Returns:
            Alerts response or None
        """
        params = {
            "limit": limit,
            "hours": hours
        }
        
        return self._make_request("GET", f"/api/v1/alerts/{symbol}", params=params)
    
    def get_24h_data(self, symbol: str) -> Optional[List[Dict]]:
        """
        Get last 24 hours of data for a cryptocurrency
        
        Args:
            symbol: Cryptocurrency symbol (BTC, ETH)
            
        Returns:
            List of price records or None
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        return self.get_historical_data(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            limit=1440,  # 24 hours * 60 minutes
            order_by="asc"  # Chronological for charting
        )
    
    def get_timeframe_data(self, symbol: str, minutes: int) -> Optional[List[Dict]]:
        """
        Get data for a specific timeframe (last N minutes)
        
        Args:
            symbol: Cryptocurrency symbol (BTC, ETH)
            minutes: Number of minutes to fetch (e.g., 60, 120, 240)
            
        Returns:
            List of price records or None
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)
        
        return self.get_historical_data(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            limit=minutes,  # One record per minute
            order_by="asc"  # Chronological for charting
        )


# Global API client instance
api_client = CryptoAPIClient()
