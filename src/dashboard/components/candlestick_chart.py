"""
Candlestick Chart Component
Phase 4 - Week 9 - Day 3-4

Displays OHLC (Open-High-Low-Close) data as professional candlestick charts.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CHART_HEIGHT, COLORS


def render_candlestick_chart(df: pd.DataFrame, symbol: str, show_volume: bool = True):
    """
    Render professional OHLC candlestick chart with volume bars
    
    Args:
        df: DataFrame with OHLC data (columns: timestamp, open, high, low, close, volume)
        symbol: Cryptocurrency symbol
        show_volume: Whether to show volume bars below chart
    """
    if df.empty:
        st.warning(f"No data available for {symbol} candlestick chart")
        return
    
    # Ensure we have required columns
    required_cols = ['timestamp', 'open', 'high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        st.error(f"Missing required columns for candlestick chart: {required_cols}")
        return
    
    # Create figure with subplots (price + volume)
    if show_volume and 'volume' in df.columns:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=(f'{symbol} Price', 'Volume')
        )
    else:
        fig = make_subplots(rows=1, cols=1)
    
    # Add candlestick trace
    fig.add_trace(
        go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name=symbol,
            increasing_line_color='#26a69a',  # Green for up
            decreasing_line_color='#ef5350',  # Red for down
            increasing_fillcolor='#26a69a',
            decreasing_fillcolor='#ef5350',
            hovertext=[
                f"Open: ${row['open']:,.2f}<br>"
                f"High: ${row['high']:,.2f}<br>"
                f"Low: ${row['low']:,.2f}<br>"
                f"Close: ${row['close']:,.2f}<br>"
                f"Time: {row['timestamp']}"
                for _, row in df.iterrows()
            ],
            hoverinfo='text'
        ),
        row=1, col=1
    )
    
    # Add volume bars if requested
    if show_volume and 'volume' in df.columns:
        # Color volume bars based on price direction
        colors = [
            COLORS['positive'] if close >= open else COLORS['negative']
            for open, close in zip(df['open'], df['close'])
        ]
        
        fig.add_trace(
            go.Bar(
                x=df['timestamp'],
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                hovertemplate='<b>%{x}</b><br>' +
                             'Volume: $%{y:,.0f}<br>' +
                             '<extra></extra>',
                showlegend=False
            ),
            row=2, col=1
        )
    
    # Update layout
    fig.update_layout(
        title=f"{symbol} - OHLC Candlestick Chart",
        height=CHART_HEIGHT + (150 if show_volume else 0),
        hovermode='x unified',
        template='plotly_dark',
        xaxis_rangeslider_visible=False,  # Hide rangeslider
        margin=dict(l=50, r=50, t=50, b=50),
        showlegend=False
    )
    
    # Update y-axis
    fig.update_yaxes(title_text="Price (USD)", tickprefix="$", tickformat=",.2f", row=1, col=1)
    
    if show_volume and 'volume' in df.columns:
        fig.update_yaxes(title_text="Volume (USD)", tickprefix="$", tickformat=",.0f", row=2, col=1)
    
    # Update x-axis
    fig.update_xaxes(title_text="Time", row=2 if show_volume else 1, col=1)
    
    # Display chart
    st.plotly_chart(fig, use_container_width=True)


def render_dual_candlestick_chart(btc_df: pd.DataFrame, eth_df: pd.DataFrame):
    """
    Render side-by-side candlestick charts for BTC and ETH
    
    Args:
        btc_df: BTC OHLC data
        eth_df: ETH OHLC data
    """
    col1, col2 = st.columns(2)
    
    with col1:
        if not btc_df.empty:
            render_candlestick_chart(btc_df, "BTC", show_volume=False)
        else:
            st.warning("No BTC data available")
    
    with col2:
        if not eth_df.empty:
            render_candlestick_chart(eth_df, "ETH", show_volume=False)
        else:
            st.warning("No ETH data available")


def add_moving_average(fig, df: pd.DataFrame, period: int, color: str, row: int = 1):
    """
    Add moving average line to chart
    
    Args:
        fig: Plotly figure object
        df: DataFrame with price data
        period: MA period (e.g., 20 for 20-period MA)
        color: Line color
        row: Subplot row number
    """
    if len(df) < period:
        return  # Not enough data for MA
    
    ma = df['close'].rolling(window=period).mean()
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=ma,
            mode='lines',
            name=f'{period}-Period MA',
            line=dict(color=color, width=1),
            hovertemplate=f'<b>{period}-MA</b><br>' +
                         'Value: $%{y:,.2f}<br>' +
                         '<extra></extra>'
        ),
        row=row, col=1
    )


def render_candlestick_with_ma(df: pd.DataFrame, symbol: str, ma_periods: list = [20, 50]):
    """
    Render candlestick chart with moving averages
    
    Args:
        df: DataFrame with OHLC data
        symbol: Cryptocurrency symbol
        ma_periods: List of MA periods to display (e.g., [20, 50])
    """
    if df.empty:
        st.warning(f"No data available for {symbol}")
        return
    
    # Create figure with volume subplot
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f'{symbol} Price with Moving Averages', 'Volume')
    )
    
    # Add candlestick
    fig.add_trace(
        go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name=symbol,
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
            increasing_fillcolor='#26a69a',
            decreasing_fillcolor='#ef5350'
        ),
        row=1, col=1
    )
    
    # Add moving averages
    ma_colors = ['#2196F3', '#FF9800', '#9C27B0']  # Blue, Orange, Purple
    for i, period in enumerate(ma_periods):
        if len(df) >= period:
            color = ma_colors[i % len(ma_colors)]
            add_moving_average(fig, df, period, color, row=1)
    
    # Add volume bars
    if 'volume' in df.columns:
        colors = [
            COLORS['positive'] if close >= open else COLORS['negative']
            for open, close in zip(df['open'], df['close'])
        ]
        
        fig.add_trace(
            go.Bar(
                x=df['timestamp'],
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                showlegend=False
            ),
            row=2, col=1
        )
    
    # Update layout
    fig.update_layout(
        height=CHART_HEIGHT + 150,
        hovermode='x unified',
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )
    
    # Update axes
    fig.update_yaxes(title_text="Price (USD)", tickprefix="$", tickformat=",.2f", row=1, col=1)
    fig.update_yaxes(title_text="Volume (USD)", tickprefix="$", tickformat=",.0f", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=1)
    
    # Display chart
    st.plotly_chart(fig, use_container_width=True)
