"""
Enhanced Statistics Component
Phase 4 - Week 9 - Day 5-7

Displays comprehensive 24h performance statistics.
"""

import streamlit as st
from typing import Dict
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def render_enhanced_stats(symbol: str):
    """
    Render enhanced 24h statistics card
    
    Args:
        symbol: Cryptocurrency symbol (BTC or ETH)
    """
    # Fetch stats from API
    stats_data = api_client.get_statistics(symbol)
    
    if not stats_data:
        st.warning(f"No statistics available for {symbol}")
        return
    
    # Create statistics card
    st.markdown(f"### 📊 {symbol} - 24 Hour Performance")
    
    # Row 1: Price metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="24h Low",
            value=format_price(stats_data.get("lowest_price", 0)),
            help="Lowest price in last 24 hours"
        )
    
    with col2:
        st.metric(
            label="24h High",
            value=format_price(stats_data.get("highest_price", 0)),
            help="Highest price in last 24 hours"
        )
    
    with col3:
        st.metric(
            label="24h Average",
            value=format_price(stats_data.get("average_price", 0)),
            help="Average price in last 24 hours"
        )
    
    with col4:
        change_pct = stats_data.get("price_change_pct", 0)
        st.metric(
            label="24h Change",
            value=format_percent(change_pct),
            delta=format_percent(change_pct),
            delta_color="normal",
            help="Percentage change from 24h low to high"
        )
    
    # Row 2: Volume and trading metrics
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric(
            label="24h Volume",
            value=format_volume(stats_data.get("total_volume", 0)),
            help="Total trading volume in last 24 hours"
        )
    
    with col6:
        st.metric(
            label="Price Range",
            value=format_price(stats_data.get("price_range", 0)),
            help="Difference between 24h high and low"
        )
    
    with col7:
        st.metric(
            label="Data Points",
            value=f"{stats_data.get('candle_count', 0):,}",
            help="Number of 1-minute candles in 24 hours"
        )
    
    with col8:
        # Calculate volatility as percentage of range to average
        avg_price = stats_data.get("average_price", 0)
        price_range = stats_data.get("price_range", 0)
        volatility = (price_range / avg_price * 100) if avg_price > 0 else 0
        
        st.metric(
            label="Volatility",
            value=f"{volatility:.2f}%",
            help="Price range as % of average (higher = more volatile)"
        )


def render_performance_summary(btc_stats: Dict, eth_stats: Dict):
    """
    Render side-by-side performance summary for BTC and ETH
    
    Args:
        btc_stats: BTC statistics data
        eth_stats: ETH statistics data
    """
    st.markdown("---")
    st.subheader("📈 24-Hour Performance Summary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if btc_stats:
            st.markdown("#### Bitcoin (BTC)")
            _render_compact_stats(btc_stats, "BTC")
        else:
            st.warning("BTC statistics unavailable")
    
    with col2:
        if eth_stats:
            st.markdown("#### Ethereum (ETH)")
            _render_compact_stats(eth_stats, "ETH")
        else:
            st.warning("ETH statistics unavailable")


def _render_compact_stats(stats: Dict, symbol: str):
    """Render compact statistics display"""
    
    low_price = format_price(stats.get('lowest_price', 0))
    high_price = format_price(stats.get('highest_price', 0))
    avg_price = format_price(stats.get('average_price', 0))
    volume = format_volume(stats.get('total_volume', 0))
    change_pct = stats.get("price_change_pct", 0)
    change_str = format_percent(change_pct)
    data_points = stats.get('candle_count', 0)
    
    # Display with metrics in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Low", low_price)
    with col2:
        st.metric("High", high_price)
    with col3:
        st.metric("Avg", avg_price)
    
    col4, col5 = st.columns(2)
    
    with col4:
        st.metric("Volume", volume)
    with col5:
        st.metric("Change", change_str, delta=change_str if change_pct != 0 else None)
    
    st.caption(f"📊 {data_points:,} data points analyzed")


# Helper functions
def format_price(price: float) -> str:
    """Format price with $ sign and 2 decimals"""
    return f"${price:,.2f}"


def format_percent(percent: float) -> str:
    """Format percentage with + or - sign"""
    return f"{percent:+.2f}%"


def format_volume(volume: float) -> str:
    """Format volume in billions"""
    if volume >= 1_000_000_000:
        return f"${volume / 1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"${volume / 1_000_000:.2f}M"
    elif volume >= 1_000:
        return f"${volume / 1_000:.2f}K"
    else:
        return f"${volume:.2f}"
