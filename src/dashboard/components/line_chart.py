"""
Line Chart Component
Phase 4 - Week 9 - Day 1-2

Displays 24-hour price trend as an interactive line chart.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CHART_HEIGHT, COLORS


def render_price_trend_chart(df: pd.DataFrame, symbol: str):
    """
    Render 24-hour price trend line chart
    
    Args:
        df: DataFrame with historical price data
        symbol: Cryptocurrency symbol
    """
    if df.empty:
        st.warning(f"No historical data available for {symbol}")
        return
    
    # Create figure
    fig = go.Figure()
    
    # Add line trace
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["close"],
        mode="lines",
        name=symbol,
        line=dict(
            color=COLORS["positive"],
            width=2
        ),
        hovertemplate="<b>%{x}</b><br>" +
                      "Price: $%{y:,.2f}<br>" +
                      "<extra></extra>"
    ))
    
    # Update layout
    fig.update_layout(
        title=f"{symbol} Price - Last 24 Hours",
        xaxis_title="Time",
        yaxis_title="Price (USD)",
        height=CHART_HEIGHT,
        hovermode="x unified",
        template="plotly_dark",
        showlegend=False,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    # Format y-axis as currency
    fig.update_yaxes(tickprefix="$", tickformat=",.2f")
    
    # Display chart
    st.plotly_chart(fig, use_container_width=True)


def render_dual_price_chart(btc_df: pd.DataFrame, eth_df: pd.DataFrame):
    """
    Render both BTC and ETH on the same chart
    
    Args:
        btc_df: BTC historical data
        eth_df: ETH historical data
    """
    if btc_df.empty and eth_df.empty:
        st.warning("No historical data available")
        return
    
    # Create figure with secondary y-axis
    fig = go.Figure()
    
    # Add BTC trace
    if not btc_df.empty:
        fig.add_trace(go.Scatter(
            x=btc_df["timestamp"],
            y=btc_df["close"],
            mode="lines",
            name="BTC",
            line=dict(color="#f7931a", width=2),  # Bitcoin orange
            hovertemplate="<b>BTC</b><br>" +
                          "%{x}<br>" +
                          "Price: $%{y:,.2f}<br>" +
                          "<extra></extra>"
        ))
    
    # Add ETH trace on secondary y-axis
    if not eth_df.empty:
        fig.add_trace(go.Scatter(
            x=eth_df["timestamp"],
            y=eth_df["close"],
            mode="lines",
            name="ETH",
            yaxis="y2",
            line=dict(color="#627eea", width=2),  # Ethereum blue
            hovertemplate="<b>ETH</b><br>" +
                          "%{x}<br>" +
                          "Price: $%{y:,.2f}<br>" +
                          "<extra></extra>"
        ))
    
    # Update layout with dual y-axes
    fig.update_layout(
        title="Price Comparison - Last 24 Hours",
        xaxis_title="Time",
        yaxis=dict(
            title="BTC Price (USD)",
            title_font=dict(color="#f7931a"),
            tickfont=dict(color="#f7931a"),
            tickprefix="$",
            tickformat=",.0f"
        ),
        yaxis2=dict(
            title="ETH Price (USD)",
            title_font=dict(color="#627eea"),
            tickfont=dict(color="#627eea"),
            tickprefix="$",
            tickformat=",.0f",
            overlaying="y",
            side="right"
        ),
        height=CHART_HEIGHT,
        hovermode="x unified",
        template="plotly_dark",
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        ),
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    # Display chart
    st.plotly_chart(fig, use_container_width=True)
