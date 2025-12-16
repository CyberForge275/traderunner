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

from axiom_bt.intraday import IntradayStore
from trading_dashboard.resolvers.timeframe_resolver import BacktestingTimeframeResolver
from trading_dashboard.callbacks._backtesting_helpers import _get_source_name
from trading_dashboard.utils.chart_preprocess import preprocess_for_chart
from trading_dashboard.utils.chart_logging import (
    generate_error_id,
    build_chart_meta,
    log_chart_meta,
    log_chart_error,
)
from visualization.plotly import build_price_chart, PriceChartConfig

logger = logging.getLogger(__name__)


def register_charts_backtesting_callbacks(app):
    """Register all callbacks for Backtesting Charts tab."""
    
    # Initialize resolver (replaces IntradayStore)
    resolver = BacktestingTimeframeResolver()
    
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
        
        try:
            # === LOAD DATA VIA RESOLVER ===
            # Resolver routes: M1/M5/M15→IntradayStore, D1→Universe, H1→Resample
            df = resolver.load(symbol, timeframe=timeframe_str, tz="America/New_York")
            
            # Track initial row count
            rows_before = len(df)
            
            if df.empty:
                # === EMPTY STATE WITH CLEAR MESSAGE ===
                empty_fig = go.Figure()
                empty_fig.add_annotation(
                    text=f"📭 No {timeframe_str} data for {symbol}<br>" +
                         f"<sub>source: {_get_source_name(timeframe_str)} | rows=0</sub>",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=16)
                )
                
                logger.warning(
                    f"source=BACKTEST_PARQUET symbol={symbol} tf={timeframe_str} "
                    f"reason=NO_ROWS rows=0"
                )
                
                return empty_fig
            
            # === USE HELPER FOR ALL TRANSFORMATIONS ===
            # Convert selected_date string to date object if provided
            ref_date = None
            if selected_date:
                ref_date = pd.to_datetime(selected_date).date()
            
            df_processed, meta = preprocess_for_chart(
                df=df,
                source="BACKTEST_PARQUET",
                ref_date=ref_date,  # Will filter if < today
                display_tz=display_tz,
                market_tz="America/New_York"
            )
            
            # === BUILD AND LOG COMPREHENSIVE CHART METADATA ===
            # Determine data path based on timeframe
            if timeframe_str == "D1":
                data_path = "data/universe/stocks_data.parquet"
            else:
                data_path = f"artifacts/data_{timeframe_str.lower()}/{symbol}.parquet"
            
            chart_meta = build_chart_meta(
                source="BACKTEST_PARQUET",
                symbol=symbol,
                timeframe=timeframe_str,
                requested_date=selected_date,
                effective_date=selected_date,  # Will enhance in P0.2
                window_mode=None,  # Will add in P0.2
                rows_before=rows_before,
                rows_after=meta['rows_after'],
                dropped_rows=meta.get('dropped_rows', 0),
                date_filter_mode="NONE" if not selected_date else "BASIC",  # Will enhance in P0.2
                min_ts=meta.get('first_ts'),
                max_ts=meta.get('last_ts'),
                market_tz=meta['market_tz'],
                display_tz=meta['display_tz'],
                session_flags={"pre": False, "after": False},  # Will read from toggles in P0.2
                data_path=data_path,
            )
            
            log_chart_meta(chart_meta)
            
            if len(df_processed) == 0:
                # Empty after preprocessing
                empty_fig = go.Figure()
                empty_fig.add_annotation(
                    text=f"📭 No data after filters for {symbol} {timeframe_str}<br>" +
                         f"<sub>Date filter may have removed all rows | rows_after={meta['rows_after']}</sub>",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=16)
                )
                return empty_fig
            
            # === BUILD CHART ===
            # For D1 (EOD data), use 'all' session mode since daily bars don't have intraday timestamps
            # For intraday (M1/M5/M15/H1), use 'rth' to filter regular trading hours
            session_mode = "all" if timeframe_str == "D1" else "rth"
            
            config = PriceChartConfig(
                title=f"{symbol} {timeframe_str} - Backtesting",
                show_volume=True,
                session_mode=session_mode,  # Critical: D1 must use 'all' to avoid empty charts
            )
            
            fig = build_price_chart(df_processed, indicators=[], config=config)
            
            return fig
            
        except Exception as e:
            # Generate error_id for correlation
            error_id = generate_error_id()
            
            # Build minimal chart_meta for error context
            error_meta = build_chart_meta(
                source="BACKTEST_PARQUET",
                symbol=symbol,
                timeframe=timeframe_str,
                requested_date=selected_date,
                effective_date=None,
                window_mode=None,
                rows_before=0,
                rows_after=0,
                dropped_rows=0,
                date_filter_mode="UNKNOWN",
                min_ts=None,
                max_ts=None,
                market_tz="America/New_York",
                display_tz=display_tz,
                session_flags={},
                data_path="unknown",
            )
            
            # Log error with full context
            log_chart_error(error_id, e, error_meta)
            
            # Show user-friendly error with error_id for correlation
            error_fig = go.Figure()
            error_fig.add_annotation(
                text=f"❌ Error loading {symbol} {timeframe_str}\u003cbr\u003e" +
                     f"\u003csub\u003e{str(e)[:80]}\u003c/sub\u003e\u003cbr\u003e" +
                     f"\u003csub\u003eerror_id={error_id}\u003c/sub\u003e",
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
