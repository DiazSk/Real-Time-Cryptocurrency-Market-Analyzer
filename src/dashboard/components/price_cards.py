"""
Price Cards Component
Phase 4 - Week 9 - Day 1-2

Displays current cryptocurrency prices with change indicators.
"""

import streamlit as st
from typing import Dict
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_processor import format_price, format_percent, get_trend_emoji


def render_price_card(price_data: Dict):
    """
    Render a price card for a cryptocurrency
    
    Args:
        price_data: Processed price data dictionary
    """
    if not price_data:
        st.error("No price data available")
        return
    
    symbol = price_data.get("symbol", "N/A")
    price = price_data.get("price", 0)
    change_pct = price_data.get("change_pct", 0)
    volume = price_data.get("volume", 0)
    
    # Get trend emoji
    trend = get_trend_emoji(change_pct)
    
    # Display using Streamlit metric
    st.metric(
        label=f"{trend} {symbol}",
        value=format_price(price),
        delta=format_percent(change_pct),
        delta_color="normal"  # Green for positive, red for negative
    )
    
    # Additional info in small text
    st.caption(f"Volume: {format_volume(volume)}")


def render_price_cards(btc_data: Dict, eth_data: Dict):
    """
    Render price cards for BTC and ETH side by side
    
    Args:
        btc_data: Processed BTC price data
        eth_data: Processed ETH price data
    """
    col1, col2 = st.columns(2)
    
    with col1:
        if btc_data:
            render_price_card(btc_data)
        else:
            st.error("BTC data unavailable")
    
    with col2:
        if eth_data:
            render_price_card(eth_data)
        else:
            st.error("ETH data unavailable")


def format_volume(volume: float) -> str:
    """Format volume with abbreviations"""
    if volume >= 1_000_000_000:
        return f"${volume / 1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"${volume / 1_000_000:.2f}M"
    elif volume >= 1_000:
        return f"${volume / 1_000:.2f}K"
    else:
        return f"${volume:.2f}"
