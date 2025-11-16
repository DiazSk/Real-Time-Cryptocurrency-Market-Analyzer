"""
Alerts Component
Phase 4 - Week 9 - Day 5-7

Displays recent price anomaly alerts.
"""

import streamlit as st
from typing import Dict, List
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.api_client import api_client


def render_alert_panel(alerts_data: Dict):
    """
    Render alerts panel with recent anomalies
    
    Args:
        alerts_data: Alerts response from API
    """
    if not alerts_data or not alerts_data.get("alerts"):
        st.info("✅ No recent price anomalies detected")
        return
    
    alerts = alerts_data.get("alerts", [])
    alert_count = len(alerts)
    
    st.subheader(f"⚠️ Recent Alerts ({alert_count})")
    
    # Display each alert
    for alert in alerts[:5]:  # Show top 5
        symbol = alert.get("symbol", "N/A")
        alert_type = alert.get("alert_type", "UNKNOWN")
        change_pct = alert.get("price_change_pct", 0)
        old_price = alert.get("old_price", 0)
        new_price = alert.get("new_price", 0)
        created_at = alert.get("created_at", "")
        
        # Parse timestamp
        try:
            alert_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            time_str = alert_time.strftime("%H:%M:%S")
        except:
            time_str = "Unknown"
        
        # Determine alert icon and color
        if alert_type == "PRICE_SPIKE":
            icon = "🚀"
            alert_color = "#26a69a"  # Green
            direction = "↗️"
        elif alert_type == "PRICE_DROP":
            icon = "📉"
            alert_color = "#ef5350"  # Red
            direction = "↘️"
        else:
            icon = "⚠️"
            alert_color = "#FF9800"  # Orange
            direction = "➡️"
        
        # Create alert card
        with st.container():
            col1, col2 = st.columns([1, 4])
            
            with col1:
                st.markdown(f"<h1 style='text-align: center; font-size: 48px;'>{icon}</h1>", 
                           unsafe_allow_html=True)
            
            with col2:
                st.markdown(
                    f"<div style='padding: 10px; border-left: 4px solid {alert_color}; background: #1e1e1e; border-radius: 5px;'>"
                    f"<strong style='font-size: 18px;'>{symbol} {alert_type.replace('_', ' ').title()}</strong><br>"
                    f"<span style='font-size: 24px; color: {alert_color};'>{direction} {format_percent(change_pct)}</span><br>"
                    f"<span style='color: #888;'>{format_price(old_price)} → {format_price(new_price)}</span><br>"
                    f"<span style='color: #666; font-size: 12px;'>⏰ {time_str}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            
            st.markdown("<br>", unsafe_allow_html=True)


def render_alerts_sidebar():
    """
    Render compact alerts in sidebar
    Fetches data from API internally
    """
    try:
        # Fetch alerts from API
        alerts_data = api_client.get_alerts(symbol="ALL", limit=10, hours=24)
        
        if not alerts_data or not alerts_data.get("alerts"):
            st.sidebar.success("✅ No recent anomalies")
            return
        
        alerts = alerts_data.get("alerts", [])
        st.sidebar.subheader(f"⚠️ Alerts ({len(alerts)})")
        
        for alert in alerts[:10]:  # Show up to 10 in sidebar
            symbol = alert.get("symbol", "N/A")
            alert_type = alert.get("alert_type", "UNKNOWN")
            change_pct = alert.get("price_change_pct", 0)
            
            # Determine icon
            icon = "🚀" if alert_type == "PRICE_SPIKE" else "📉"
            
            # Compact display
            st.sidebar.markdown(
                f"{icon} **{symbol}** {format_percent(change_pct)}",
                unsafe_allow_html=True
            )
        
        st.sidebar.markdown("---")
    except Exception as e:
        st.sidebar.warning(f"Unable to load alerts: {str(e)}")


def render_alert_summary(alerts_data: Dict):
    """
    Render alert summary statistics
    
    Args:
        alerts_data: Alerts response from API
    """
    if not alerts_data or not alerts_data.get("alerts"):
        return
    
    alerts = alerts_data.get("alerts", [])
    
    # Count alert types
    spikes = sum(1 for a in alerts if a.get("alert_type") == "PRICE_SPIKE")
    drops = sum(1 for a in alerts if a.get("alert_type") == "PRICE_DROP")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Alerts", len(alerts))
    
    with col2:
        st.metric("Price Spikes 🚀", spikes)
    
    with col3:
        st.metric("Price Drops 📉", drops)


# Helper functions
def format_price(price: float) -> str:
    """Format price with $ sign and 2 decimals"""
    return f"${price:,.2f}"


def format_percent(percent: float) -> str:
    """Format percentage with + or - sign"""
    return f"{percent:+.2f}%"
