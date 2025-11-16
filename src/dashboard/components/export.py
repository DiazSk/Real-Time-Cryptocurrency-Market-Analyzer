"""
Export Component
Phase 4 - Week 9 - Day 5-7

Provides data export functionality (CSV download).
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import io


def create_csv_download(df: pd.DataFrame, filename_prefix: str = "crypto_data"):
    """
    Create CSV download button for DataFrame
    
    Args:
        df: DataFrame to export
        filename_prefix: Prefix for filename
    
    Returns:
        CSV string buffer
    """
    if df.empty:
        return None
    
    # Create filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.csv"
    
    # Convert DataFrame to CSV
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_string = csv_buffer.getvalue()
    
    return csv_string, filename


def render_export_buttons(btc_df: pd.DataFrame, eth_df: pd.DataFrame):
    """
    Render export buttons for downloading data
    
    Args:
        btc_df: BTC historical data
        eth_df: ETH historical data
    """
    st.markdown("---")
    st.subheader("💾 Export Data")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not btc_df.empty:
            csv_data, filename = create_csv_download(btc_df, "BTC_data")
            st.download_button(
                label="📥 Download BTC Data",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                help="Download BTC price data as CSV"
            )
        else:
            st.button("📥 Download BTC Data", disabled=True)
    
    with col2:
        if not eth_df.empty:
            csv_data, filename = create_csv_download(eth_df, "ETH_data")
            st.download_button(
                label="📥 Download ETH Data",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                help="Download ETH price data as CSV"
            )
        else:
            st.button("📥 Download ETH Data", disabled=True)
    
    with col3:
        # Combined export
        if not btc_df.empty and not eth_df.empty:
            # Combine both DataFrames
            btc_df_export = btc_df.copy()
            eth_df_export = eth_df.copy()
            
            btc_df_export['symbol'] = 'BTC'
            eth_df_export['symbol'] = 'ETH'
            
            combined_df = pd.concat([btc_df_export, eth_df_export], ignore_index=True)
            combined_df = combined_df.sort_values('timestamp')
            
            csv_data, filename = create_csv_download(combined_df, "BTC_ETH_combined")
            st.download_button(
                label="📥 Download Both",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                help="Download combined BTC + ETH data as CSV"
            )
        else:
            st.button("📥 Download Both", disabled=True)
