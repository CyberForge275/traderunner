"""
Backtesting Charts Callbacks
=============================

CRITICAL ARCHITECTURE RULES:
- This module MUST NOT import sqlite3 or LiveCandlesRepository
- Data source: Parquet ONLY (via IntradayStore)
- Architecture tests enforce these constraints

Data Flow:
1. Load from Parquet (tz-aware in America/New_York)
2. Apply date filtering if selected (in market TZ)
3. Apply session filtering if toggled (in market TZ)
4. Convert to display TZ if requested (Berlin)
5. Row count MUST stay identical across TZ conversion
"""

from dash import Input, Output, State, callback_context
import plotly.graph_objs as go
import pandas as pd
import logging
from datetime import date

from axiom_bt.intraday import IntradayStore, Timeframe
from visualization.plotly import build_price_chart, PriceChartConfig

logger = logging.getLogger(__name__)


def register_charts_backtesting_callbacks(app):
    """Register all callbacks for Backtesting Charts tab."""
    
    # Initialize store
    intraday_store = IntradayStore()
    
    @app.callback(
        Output("bt-candlestick-chart", "figure"),
        [
            Input("bt-symbol-selector", "value"),
            Input("bt-tf-m1", "n_clicks"),
            Input("bt-tf-m5", "n_clicks"),
            Input("bt-tf-m15", "n_clicks"),
            Input("bt-tf-h1", "n_clicks"),
            Input("bt-tf-d1", "n_clicks"),
            Input("bt-tz-ny-btn", "n_clicks"),
            Input("bt-tz-berlin-btn", "n_clicks"),
            Input("bt-refresh-btn", "n_clicks"),
            Input("bt-date-picker", "date"),
            Input("bt-session-toggles", "value"),
        ],
        prevent_initial_call=False
    )
    def update_backtesting_chart(
        symbol, m1_clicks, m5_clicks, m15_clicks, h1_clicks, d1_clicks,
        ny_clicks, berlin_clicks, refresh_clicks, selected_date, session_toggles
    ):
        """
        Update backtesting chart with data from Parquet.
        
        CRITICAL: Timezone toggle changes DISPLAY only, not data filtering.
        """
        # Determine active timeframe
        ctx = callback_context
        timeframe_str = "M5"  # Default
        
        if ctx.triggered:
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if button_id == 'bt-tf-m1':
                timeframe_str = "M1"
            elif button_id == 'bt-tf-m5':
                timeframe_str = "M5"
            elif button_id == 'bt-tf-m15':
                timeframe_str = "M15"
            elif button_id == 'bt-tf-h1':
                timeframe_str = "H1"
            elif button_id == 'bt-tf-d1':
                timeframe_str = "D1"
        
        # Determine display timezone
        display_tz = "America/New_York"  # Default
        if ctx.triggered:
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if button_id == 'bt-tz-berlin-btn':
                display_tz = "Europe/Berlin"
        
        # Validate inputs
        if not symbol:
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text="⚠️ No symbol selected",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="orange")
            )
            return empty_fig
        
        # === CRITICAL LOGGING ===
        logger.info(
            f"source=BACKTEST_PARQUET symbol={symbol} tf={timeframe_str} "
            f"display_tz={display_tz} market_tz=America/New_York date_filter={selected_date}"
        )
        
        try:
            # === LOAD DATA FROM PARQUET ===
            timeframe = Timeframe(timeframe_str)
            df = intraday_store.load(symbol, timeframe=timeframe)
            
            rows_after_load = len(df)
            
            if df.empty:
                # === EMPTY STATE WITH EXPLANATION ===
                empty_fig = go.Figure()
                empty_fig.add_annotation(
                    text=f"📭 No backtest data for {symbol} {timeframe_str}<br>" +
                         f"<sub>source: BACKTEST_PARQUET | rows=0</sub>",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=16)
                )
                
                logger.warning(
                    f"source=BACKTEST_PARQUET symbol={symbol} tf={timeframe_str} "
                    f"reason=NO_ROWS rows=0"
                )
                
                return empty_fig
            
            # === DATE FILTERING (Optional, in market TZ) ===
            # Note: This happens BEFORE timezone conversion
            if selected_date:
                ref_date = pd.to_datetime(selected_date).date()
                today = date.today()
                
                if ref_date < today:
                    # Historical date - filter to that day
                    df = df[df.index.date == ref_date]
                    logger.info(f"📅 Filtered to date: {ref_date}")
            
            # === DROP NaN ROWS ===
            rows_before_dropna = len(df)
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            rows_after_dropna = len(df)
            
            if rows_before_dropna > rows_after_dropna:
                logger.debug(
                    f"🧹 Dropped {rows_before_dropna - rows_after_dropna} NaN rows "
                    f"({rows_after_dropna} valid bars remaining)"
                )
            
            if df.empty:
                empty_fig = go.Figure()
                empty_fig.add_annotation(
                    text=f"📭 No data after filters for {symbol} {timeframe_str}<br>" +
                         f"<sub>Date filter may have removed all rows</sub>",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=16)
                )
                return empty_fig
            
            # === TIMEZONE CONVERSION FOR DISPLAY ===
            # CRITICAL: This MUST NOT change row count
            if display_tz != "America/New_York":
                df.index = df.index.tz_convert(display_tz)
            
            rows_after_tz_conversion = len(df)
            
            # === INVARIANT CHECK ===
            assert rows_after_dropna == rows_after_tz_conversion, (
                f"TZ conversion changed row count! "
                f"Before: {rows_after_dropna}, After: {rows_after_tz_conversion}"
            )
            
            # === BUILD CHART ===
            config = PriceChartConfig(
                title=f"{symbol} {timeframe_str} - Backtesting",
                timezone=display_tz,
                show_volume=True,
            )
            
            fig = build_price_chart(df, indicators=[], config=config)
            
            # === FINAL LOGGING ===
            first_ts = df.index[0] if len(df) > 0 else None
            last_ts = df.index[-1] if len(df) > 0 else None
            
            logger.info(
                f"source=BACKTEST_PARQUET symbol={symbol} tf={timeframe_str} rows={len(df)} "
                f"first_ts={first_ts} last_ts={last_ts} "
                f"market_tz=America/New_York display_tz={display_tz}"
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error loading backtesting chart: {e}", exc_info=True)
            
            error_fig = go.Figure()
            error_fig.add_annotation(
                text=f"❌ Error loading {symbol} {timeframe_str}<br>" +
                     f"<sub>{str(e)[:100]}</sub>",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="red")
            )
            
            return error_fig
    
    
    @app.callback(
        [
            Output("bt-tf-m1", "active"),
            Output("bt-tf-m5", "active"),
            Output("bt-tf-m15", "active"),
            Output("bt-tf-h1", "active"),
            Output("bt-tf-d1", "active"),
        ],
        [
            Input("bt-tf-m1", "n_clicks"),
            Input("bt-tf-m5", "n_clicks"),
            Input("bt-tf-m15", "n_clicks"),
            Input("bt-tf-h1", "n_clicks"),
            Input("bt-tf-d1", "n_clicks"),
        ]
    )
    def update_timeframe_buttons(m1, m5, m15, h1, d1):
        """Update which timeframe button is active."""
        ctx = callback_context
        if not ctx.triggered:
            return False, True, False, False, False  # M5 default
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        return (
            button_id == 'bt-tf-m1',
            button_id == 'bt-tf-m5',
            button_id == 'bt-tf-m15',
            button_id == 'bt-tf-h1',
            button_id == 'bt-tf-d1',
        )
    
    
    @app.callback(
        [
            Output("bt-tz-ny-btn", "active"),
            Output("bt-tz-berlin-btn", "active"),
            Output("bt-tz-ny-btn", "outline"),
            Output("bt-tz-berlin-btn", "outline"),
        ],
        [
            Input("bt-tz-ny-btn", "n_clicks"),
            Input("bt-tz-berlin-btn", "n_clicks"),
        ]
    )
    def update_timezone_buttons(ny, berlin):
        """Update which timezone button is active."""
        ctx = callback_context
        if not ctx.triggered:
            return True, False, False, True  # NY default
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'bt-tz-ny-btn':
            return True, False, False, True
        else:
            return False, True, True, False
