"""
Dashboard Configuration Settings
Phase 4 - Week 9 - Day 1-2
"""

# API Configuration
API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 10  # seconds

# Refresh Settings
REFRESH_INTERVAL = 2  # seconds (how often to update data)

# Supported Cryptocurrencies
SYMBOLS = ["BTC", "ETH"]

# Chart Settings
DEFAULT_TIMEFRAME = "24h"  # Default historical data timeframe
CHART_HEIGHT = 400

# Color Scheme
COLORS = {
    "positive": "#26a69a",  # Green for price increases
    "negative": "#ef5350",  # Red for price decreases
    "neutral": "#78909c",   # Gray for neutral
    "background": "#0e1117", # Dark background
    "text": "#fafafa"       # Light text
}

# Display Formats
PRICE_FORMAT = "${:,.2f}"
PERCENT_FORMAT = "{:+.2f}%"
VOLUME_FORMAT = "${:,.0f}"

# Data Refresh
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
