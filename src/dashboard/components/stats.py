"""
Statistics Component
Phase 4 - Week 9 - Day 1-2

Displays statistical summaries for cryptocurrencies.
"""

import streamlit as st
from typing import Dict
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_processor import format_price, format_percent, format_volume


def render_stats_card(stats_data: Dict):
    """
    Render statistics card for a cryptocurrency
    
    Args:
        stats_data: Processed statistics data
    """
    if not stats_data:
        st.warning("No statistics available")
        return
    
    symbol = stats_data.get("symbol", "N/A")
    
    st.subheader(f"{symbol} 24h Statistics")
    
    # Create columns for stats
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="24h Low",
            value=format_price(stats_data.get("lowest", 0))
        )
    
    with col2:
        st.metric(
            label="24h High",
            value=format_price(stats_data.get("highest", 0))
        )
    
    with col3:
        st.metric(
            label="24h Average",
            value=format_price(stats_data.get("average", 0))
        )
    
    # Second row of stats
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.metric(
            label="24h Volume",
            value=format_volume(stats_data.get("total_volume", 0))
        )
    
    with col5:
        st.metric(
            label="Price Range",
            value=format_price(stats_data.get("price_range", 0))
        )
    
    with col6:
        st.metric(
            label="24h Change",
            value=format_percent(stats_data.get("change_pct", 0)),
            delta=format_percent(stats_data.get("change_pct", 0)),
            delta_color="normal"
        )


def render_quick_stats(btc_data: Dict, eth_data: Dict):
    """
    Render quick stats row for both cryptocurrencies
    
    Args:
        btc_data: BTC price data
        eth_data: ETH price data
    """
    st.markdown("---")
    st.subheader("📊 Quick Stats")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if btc_data:
            st.metric(
                label="BTC High",
                value=format_price(btc_data.get("high", 0))
            )
    
    with col2:
        if btc_data:
            st.metric(
                label="BTC Low",
                value=format_price(btc_data.get("low", 0))
            )
    
    with col3:
        if eth_data:
            st.metric(
                label="ETH High",
                value=format_price(eth_data.get("high", 0))
            )
    
    with col4:
        if eth_data:
            st.metric(
                label="ETH Low",
                value=format_price(eth_data.get("low", 0))
            )
