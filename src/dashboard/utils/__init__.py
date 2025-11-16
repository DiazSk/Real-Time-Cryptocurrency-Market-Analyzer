"""
Dashboard Utilities Package
"""

# Utilities are imported directly in app.py to avoid relative import issues
__all__ = [
    "api_client",
    "get_api_client",
    "format_price",
    "format_percent",
    "format_volume",
    "process_latest_price",
    "process_historical_data",
    "process_statistics",
    "get_color_for_change",
    "get_trend_emoji"
]
