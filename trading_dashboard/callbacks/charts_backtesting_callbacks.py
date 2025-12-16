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
from trading_dashboard.utils.date_filtering import (
    calculate_effective_date,
    apply_d1_window,
    apply_intraday_exact_day,
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
            Input("bt-date-picker", "date"),
            Input("bt-window-selector", "value"),  # NEW: Window for D1
            Input("bt-tz-ny-btn", "n_clicks"),
            Input("bt-tz-berlin-btn", "n_clicks"),
            Input("bt-refresh-btn", "n_clicks"),
            Input("bt-session-toggles", "value"),
        ],
        prevent_initial_call=False
    )
    def update_backtesting_chart(
        symbol, m1_clicks, m5_clicks, m15_clicks, h1_clicks, d1_clicks,
        selected_date, window,  # NEW: window parameter
        ny_clicks, berlin_clicks, refresh_clicks, session_toggles
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
            
            # === APPLY DATE FILTERING (P0.2) ===
            # Convert selected_date string to date object if provided
            requested_date = None
            if selected_date:
                requested_date = pd.to_datetime(selected_date).date()
            
            # Calculate effective date (with clamping/rollback)
            effective_date, date_reason = calculate_effective_date(requested_date, df)
            
            # Apply timeframe-specific filtering
            date_filter_mode = "NONE"
            if timeframe_str == "D1":
                # D1: Window-based filtering
                df = apply_d1_window(df, effective_date, window=window or "12M")
                date_filter_mode = f"D1_WINDOW_{window or '12M'}"
            else:
                # Intraday (M1/M5/M15/H1): Exact-day filtering
                if requested_date:
                    df = apply_intraday_exact_day(df, effective_date, market_tz="America/New_York")
                    date_filter_mode = "INTRADAY_EXACT_DAY"
                else:
                    # No date filter - show recent data (last N days)
                    date_filter_mode = "INTRADAY_RECENT"
            
            # Check if filtering removed all data
            if df.empty:
                empty_fig = go.Figure()
                empty_fig.add_annotation(
                    text=f"📭 No data for {symbol} {timeframe_str} on {effective_date.date()}<br>" +
                         f"<sub>Date filter removed all rows | Available range: {rows_before} rows total</sub>",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=16)
                )
                return empty_fig
            
            # === USE HELPER FOR ALL TRANSFORMATIONS ===
            # Note: ref_date=None here because we already applied date filtering above
            df_processed, meta = preprocess_for_chart(
                df=df,
                source="BACKTEST_PARQUET",
                ref_date=None,  # Already filtered above
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
                requested_date=str(requested_date) if requested_date else None,
                effective_date=str(effective_date.date()) if effective_date else None,
                window_mode=window if timeframe_str == "D1" else None,
                rows_before=rows_before,
                rows_after=len(df),  # After date filtering
                dropped_rows=rows_before - len(df),
                date_filter_mode=date_filter_mode,
                min_ts=df.index.min() if len(df) > 0 else None,
                max_ts=df.index.max() if len(df) > 0 else None,
                market_tz="America/New_York",
                display_tz=display_tz,
                session_flags={"pre": "pre" in (session_toggles or []), "after": "after" in (session_toggles or [])},
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
            
            # Calculate uirevision for persistent zoom
            # Zoom resets only when these change: symbol, tf, effective_date, window, display_tz, sessions
            session_hash = f"{session_toggles or []}"
            uirevision = f"{symbol}|{timeframe_str}|{effective_date.date() if effective_date else 'none'}|{window if timeframe_str == 'D1' else 'na'}|{display_tz}|{session_hash}"
            
            config = PriceChartConfig(
                title=f"{symbol} {timeframe_str} - Backtesting",
                show_volume=True,
                session_mode=session_mode,  # Critical: D1 must use 'all' to avoid empty charts
                show_rangeslider=(timeframe_str == "D1"),  # Rangeslider only for D1
            )
            
            fig = build_price_chart(df_processed, indicators=[], config=config)
            
            # Apply uirevision and dragmode to layout
            fig.update_layout(
                uirevision=uirevision,  # Persistent zoom state
                dragmode='zoom',  # Default interaction mode
            )
            
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
    
    
    @app.callback(
        Output("bt-availability-box", "children"),
        [
            Input("bt-symbol-selector", "value"),
            Input("bt-availability-refresh", "n_clicks"),
        ],
    )
    def update_availability_display(symbol, refresh_clicks):
        """
        Update data availability display for selected symbol.
        
        Thin callback - delegates to service layer.
        """
        from trading_dashboard.services.data_availability_service import (
            get_availability,
            format_availability_for_ui
        )
        
        if not symbol:
            return html.Div(
                "Select symbol",
                className="text-muted",
                style={"textAlign": "center", "padding": "20px 0"}
            )
        
        # Check if refresh button was clicked
        ctx = callback_context
        force_refresh = (ctx.triggered and 
                        ctx.triggered[0]['prop_id'] == 'bt-availability-refresh.n_clicks')
        
        # Delegate to service layer
        try:
            result = get_availability(symbol, force_refresh=force_refresh)
            return format_availability_for_ui(result)
        except Exception as e:
            logger.error(f"Error getting availability for {symbol}: {e}", exc_info=True)
            return html.Div(
                f"Error: {str(e)[:40]}",
                style={"color": "red", "fontSize": "0.7rem"}
            )
