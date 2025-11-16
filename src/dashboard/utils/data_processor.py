"""
Data Processing Utilities
Phase 4 - Week 9 - Day 1-2

Helper functions for data transformation and formatting.
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional


def format_price(price: float) -> str:
    """Format price as currency"""
    return f"${price:,.2f}"


def format_percent(value: float) -> str:
    """Format percentage with sign"""
    return f"{value:+.2f}%"


def format_volume(volume: float) -> str:
    """Format volume as abbreviated currency"""
    if volume >= 1_000_000_000:
        return f"${volume / 1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"${volume / 1_000_000:.2f}M"
    elif volume >= 1_000:
        return f"${volume / 1_000:.2f}K"
    else:
        return f"${volume:.2f}"


def calculate_price_change(current: float, previous: float) -> float:
    """Calculate percentage change between two prices"""
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def process_latest_price(data: Dict) -> Dict:
    """
    Process latest price data from API
    
    Args:
        data: Raw API response
        
    Returns:
        Processed price data with calculated fields
    """
    if not data:
        return {}
    
    # Calculate price change from open to close
    price_change_pct = calculate_price_change(
        float(data.get("close", 0)),
        float(data.get("open", 0))
    )
    
    return {
        "symbol": data.get("symbol"),
        "price": float(data.get("close", 0)),
        "open": float(data.get("open", 0)),
        "high": float(data.get("high", 0)),
        "low": float(data.get("low", 0)),
        "volume": float(data.get("volume_sum", 0)),
        "change_pct": price_change_pct,
        "event_count": data.get("event_count", 0),
        "window_start": data.get("window_start"),
        "window_end": data.get("window_end")
    }


def process_historical_data(data: List[Dict]) -> pd.DataFrame:
    """
    Convert historical data list to pandas DataFrame
    
    Args:
        data: List of historical price records
        
    Returns:
        DataFrame with processed price data
    """
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Convert timestamp columns to datetime
    if "window_start" in df.columns:
        df["window_start"] = pd.to_datetime(df["window_start"])
    
    # Rename columns for clarity
    column_mapping = {
        "window_start": "timestamp",
        "open_price": "open",
        "high_price": "high",
        "low_price": "low",
        "close_price": "close",
        "volume_sum": "volume",
        "trade_count": "trades"
    }
    
    df = df.rename(columns=column_mapping)
    
    # Convert numeric columns to float
    numeric_columns = ["open", "high", "low", "close", "volume"]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # Calculate price change
    if "open" in df.columns and "close" in df.columns:
        df["change_pct"] = df.apply(
            lambda row: calculate_price_change(row["close"], row["open"]),
            axis=1
        )
    
    # Sort by timestamp
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp")
    
    return df


def process_statistics(data: Dict) -> Dict:
    """
    Process statistics data from API
    
    Args:
        data: Raw statistics response
        
    Returns:
        Formatted statistics
    """
    if not data:
        return {}
    
    return {
        "symbol": data.get("symbol"),
        "lowest": float(data.get("lowest_price", 0)),
        "highest": float(data.get("highest_price", 0)),
        "average": float(data.get("average_price", 0)),
        "total_volume": float(data.get("total_volume", 0)),
        "candle_count": data.get("candle_count", 0),
        "price_range": float(data.get("price_range", 0)),
        "change_pct": float(data.get("price_change_pct", 0))
    }


def get_color_for_change(change_pct: float) -> str:
    """
    Get color based on price change
    
    Args:
        change_pct: Percentage change
        
    Returns:
        Color string (green for positive, red for negative)
    """
    if change_pct > 0:
        return "#26a69a"  # Green
    elif change_pct < 0:
        return "#ef5350"  # Red
    else:
        return "#78909c"  # Gray


def get_trend_emoji(change_pct: float) -> str:
    """
    Get trend emoji based on price change
    
    Args:
        change_pct: Percentage change
        
    Returns:
        Emoji string
    """
    if change_pct > 2:
        return "🚀"
    elif change_pct > 0:
        return "📈"
    elif change_pct < -2:
        return "📉"
    elif change_pct < 0:
        return "↘️"
    else:
        return "➡️"
