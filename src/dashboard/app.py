"""
Real-Time Cryptocurrency Market Analyzer Dashboard
Phase 4 - Week 9 - Day 5-7 Enhanced

Main Streamlit application with alerts, enhanced stats, and export functionality.
"""

import streamlit as st
from datetime import datetime
import logging
import pandas as pd
import time
import sys
from pathlib import Path

# Add dashboard directory to path for absolute imports
dashboard_dir = Path(__file__).parent
sys.path.insert(0, str(dashboard_dir))

# Import dashboard components
from components.price_cards import render_price_cards
from components.line_chart import render_dual_price_chart
from components.stats import render_quick_stats

# Import candlestick components
from components.candlestick_chart import (
    render_candlestick_chart,
    render_dual_candlestick_chart,
    render_candlestick_with_ma
)

# Import new components
from components.alerts import render_alert_panel, render_alerts_sidebar
from components.enhanced_stats import render_enhanced_stats, render_performance_summary
from components.export import render_export_buttons

# Import utilities
from utils.api_client import api_client
from utils.data_processor import process_latest_price, process_historical_data

from config import REFRESH_INTERVAL, SYMBOLS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Crypto Market Analyzer",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main {
        padding-top: 2rem;
    }
    h1 {
        color: #26a69a;
        text-align: center;
    }
    .stMetric {
        background-color: #1e1e1e;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #333;
    }
    .stAlert {
        background-color: #1e1e1e;
        border: 1px solid #ef5350;
    }
    .stRadio > div {
        flex-direction: row;
        gap: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def fetch_latest_prices():
    """Fetch latest prices for all cryptocurrencies"""
    try:
        response = api_client.get_all_latest_prices()
        
        if response and "prices" in response:
            btc_raw = response["prices"].get("BTC")
            eth_raw = response["prices"].get("ETH")
            
            btc_data = process_latest_price(btc_raw) if btc_raw else None
            eth_data = process_latest_price(eth_raw) if eth_raw else None
            
            return btc_data, eth_data
        else:
            # Fallback to individual requests
            btc_raw = api_client.get_latest_price("BTC")
            eth_raw = api_client.get_latest_price("ETH")
            
            btc_data = process_latest_price(btc_raw) if btc_raw else None
            eth_data = process_latest_price(eth_raw) if eth_raw else None
            
            return btc_data, eth_data
            
    except Exception as e:
        logger.error(f"Error fetching latest prices: {e}")
        return None, None


def fetch_timeframe_data(symbol: str, minutes: int):
    """Fetch data for specific timeframe"""
    try:
        data = api_client.get_timeframe_data(symbol, minutes)
        if data:
            return process_historical_data(data)
        return None
    except Exception as e:
        logger.error(f"Error fetching {minutes}min data for {symbol}: {e}")
        return None


def main():
    """Main dashboard application"""
    
    # Sidebar configuration
    with st.sidebar:
        st.title("🪙 Crypto Analyzer")
        st.markdown("---")
        
        # About section
        with st.expander("ℹ️ About This Project", expanded=False):
            st.markdown("""
            **Real-Time Cryptocurrency Market Analyzer**
            
            A production-grade streaming data platform built with:
            - Apache Kafka (message streaming)
            - Apache Flink (stream processing)
            - Redis (caching layer)
            - PostgreSQL (time-series storage)
            - FastAPI (REST + WebSocket)
            - Streamlit (visualization)
            
            **Features:**
            - Real-time price tracking
            - OHLC aggregation (1m, 5m, 15m)
            - Anomaly detection (±5% spikes)
            - Event-driven updates (Redis Pub/Sub)
            - Professional candlestick charts
            - Technical indicators (MA)
            
            **Author:** Zaid
            **Purpose:** FAANG internship portfolio project
            """)
        
        st.markdown("---")
        
        # Display alerts in sidebar
        render_alerts_sidebar()
        
        # System status
        st.markdown("---")
        st.markdown("### System Status")
        health = api_client.get_health()
        if health and health.get("status") == "healthy":
            st.success("✅ All Systems Operational")
            services = health.get("services", {})
            for service, status in services.items():
                icon = "✅" if status == "healthy" else "❌"
                st.caption(f"{icon} {service.title()}: {status}")
        else:
            st.error("❌ API Offline")
    
    # Main content
    # Title
    st.title("🪙 Real-Time Cryptocurrency Market Analyzer")
    st.markdown("### Live Price Tracking with Event-Driven Updates")
    
    # Check API health
    health = api_client.get_health()
    if not health or health.get("status") != "healthy":
        st.error("⚠️ API is not responding. Please check if the backend is running.")
        st.code("Start API: START_API.bat", language="bash")
        st.stop()
    
    # Fetch latest prices
    with st.spinner("Loading latest prices..."):
        btc_data, eth_data = fetch_latest_prices()
    
    if not btc_data and not eth_data:
        st.error("❌ Unable to fetch price data. Please ensure the data pipeline is running.")
        st.code("""
Start Producer: START_PRODUCER.bat
Wait 2 minutes for data to flow through pipeline
        """, language="bash")
        st.stop()
    
    # Display price cards
    st.markdown("---")
    render_price_cards(btc_data, eth_data)
    
    # Display quick stats
    if btc_data or eth_data:
        render_quick_stats(btc_data, eth_data)
    
    # Alerts panel
    st.markdown("---")
    alerts_data = api_client.get_alerts(symbol="ALL", limit=5, hours=24)
    if alerts_data and alerts_data.get("alert_count", 0) > 0:
        render_alert_panel(alerts_data)
    
    # Enhanced Statistics
    st.markdown("---")
    
    # Fetch statistics for both symbols
    btc_stats = api_client.get_statistics("BTC")
    eth_stats = api_client.get_statistics("ETH")
    
    if btc_stats or eth_stats:
        render_performance_summary(btc_stats, eth_stats)
    
    # Chart Selection Section
    st.markdown("---")
    st.subheader("📊 Price Visualization")
    
    # Timeframe selector
    col1, col2 = st.columns([1, 3])
    
    with col1:
        timeframe = st.selectbox(
            "Show Last:",
            ["15 Minutes", "30 Minutes", "1 Hour", "2 Hours", "4 Hours", "24 Hours"],
            key="timeframe_selector",
            help="Display the most recent N minutes of 1-minute candles"
        )
    
    with col2:
        chart_style = st.radio(
            "Chart Style:",
            ["Candlestick", "Line Chart", "Candlestick with MA"],
            horizontal=True,
            key="chart_style"
        )
    
    # Map timeframe to minutes (for fetching 1-min candles from last N minutes)
    timeframe_map = {
        "15 Minutes": 15,
        "30 Minutes": 30,
        "1 Hour": 60,
        "2 Hours": 120,
        "4 Hours": 240,
        "24 Hours": 1440
    }
    
    selected_minutes = timeframe_map[timeframe]
    
    # Symbol selector for single view
    symbol_view = st.radio(
        "View:",
        ["Both (Side by Side)", "BTC", "ETH"],
        horizontal=True,
        key="symbol_view"
    )
    
    # Fetch data based on selection
    with st.spinner(f"Loading {timeframe.lower()} data..."):
        if symbol_view == "Both (Side by Side)":
            btc_df = fetch_timeframe_data("BTC", selected_minutes)
            eth_df = fetch_timeframe_data("ETH", selected_minutes)
        elif symbol_view == "BTC":
            btc_df = fetch_timeframe_data("BTC", selected_minutes)
            eth_df = None
        else:  # ETH
            btc_df = None
            eth_df = fetch_timeframe_data("ETH", selected_minutes)
    
    # Render charts based on style
    if chart_style == "Candlestick":
        if symbol_view == "Both (Side by Side)":
            if btc_df is not None or eth_df is not None:
                render_dual_candlestick_chart(
                    btc_df if btc_df is not None else pd.DataFrame(),
                    eth_df if eth_df is not None else pd.DataFrame()
                )
            else:
                st.warning("No data available for candlestick chart")
        
        elif symbol_view == "BTC" and btc_df is not None:
            render_candlestick_chart(btc_df, "BTC", show_volume=True)
        
        elif symbol_view == "ETH" and eth_df is not None:
            render_candlestick_chart(eth_df, "ETH", show_volume=True)
        
        else:
            st.warning(f"No data available for {symbol_view}")
    
    elif chart_style == "Line Chart":
        if symbol_view == "Both (Side by Side)":
            if btc_df is not None or eth_df is not None:
                render_dual_price_chart(
                    btc_df if btc_df is not None else pd.DataFrame(),
                    eth_df if eth_df is not None else pd.DataFrame()
                )
            else:
                st.warning("No historical data available")
        
        elif symbol_view == "BTC" and btc_df is not None:
            from components.line_chart import render_price_trend_chart
            render_price_trend_chart(btc_df, "BTC")
        
        elif symbol_view == "ETH" and eth_df is not None:
            from components.line_chart import render_price_trend_chart
            render_price_trend_chart(eth_df, "ETH")
        
        else:
            st.warning(f"No data available for {symbol_view}")
    
    elif chart_style == "Candlestick with MA":
        if symbol_view == "Both (Side by Side)":
            st.info("Moving averages are only available in single-symbol view. Please select BTC or ETH.")
        
        elif symbol_view == "BTC" and btc_df is not None:
            render_candlestick_with_ma(btc_df, "BTC", ma_periods=[20, 50])
        
        elif symbol_view == "ETH" and eth_df is not None:
            render_candlestick_with_ma(eth_df, "ETH", ma_periods=[20, 50])
        
        else:
            st.warning(f"No data available for {symbol_view}")
    
    # Export functionality
    if (btc_df is not None and not btc_df.empty) or (eth_df is not None and not eth_df.empty):
        render_export_buttons(
            btc_df if btc_df is not None else pd.DataFrame(),
            eth_df if eth_df is not None else pd.DataFrame()
        )
    
    # Footer with last update time
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        st.info(f"🔄 Last updated: {current_time} | Refreshing every {REFRESH_INTERVAL}s")
        st.caption("Data flows: CoinGecko → Kafka → Flink → Redis/PostgreSQL → FastAPI → Dashboard")
    
    # Auto-refresh
    time.sleep(REFRESH_INTERVAL)
    st.rerun()


if __name__ == "__main__":
    main()
