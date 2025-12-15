"""
Live Charts Callbacks
=====================

CRITICAL ARCHITECTURE RULES:
- This module MUST NOT import IntradayStore or read_parquet
- Data source: SQLite ONLY (via LiveCandlesRepository)
- Timezone toggle is DISPLAY ONLY (never filters data)
- Architecture tests enforce these constraints

Data Flow:
1. Load from SQLite (tz-aware in America/New_York)
2. NO date filtering (always latest)
3. NO session filtering (always all sessions)
4. Apply LIMIT only
5. Convert to display TZ if requested (Berlin)
6. Row count MUST stay identical across TZ conversion
"""

from dash import Input, Output, State, callback_context
import plotly.graph_objs as go
import pandas as pd
import logging

from trading_dashboard.repositories.live_candles import LiveCandlesRepository
from visualization.plotly import build_price_chart, PriceChartConfig

logger = logging.getLogger(__name__)


def register_charts_live_callbacks(app):
    """Register all callbacks for Live Charts tab."""
    
    # Initialize repository
    live_repo = LiveCandlesRepository()
    
    @app.callback(
        [
            Output("live-candlestick-chart", "figure"),
            Output("live-freshness-text", "children"),
            Output("live-freshness-badge", "children"),
        ],
        [
            Input("live-symbol-selector", "value"),
            Input("live-tf-m1", "n_clicks"),
            Input("live-tf-m5", "n_clicks"),
            Input("live-tf-m15", "n_clicks"),
            Input("live-tz-ny-btn", "n_clicks"),
            Input("live-tz-berlin-btn", "n_clicks"),
            Input("live-refresh-btn", "n_clicks"),
        ],
        prevent_initial_call=False
    )
    def update_live_chart(symbol, m1_clicks, m5_clicks, m15_clicks, ny_clicks, berlin_clicks, refresh_clicks):
        """
        Update live chart with data from SQLite.
        
        CRITICAL: Timezone toggle changes DISPLAY only, not data filtering.
        """
        # Determine active timeframe
        ctx = callback_context
        timeframe = "M5"  # Default
        
        if ctx.triggered:
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if button_id == 'live-tf-m1':
                timeframe = "M1"
            elif button_id == 'live-tf-m5':
                timeframe = "M5"
            elif button_id == 'live-tf-m15':
                timeframe = "M15"
        
        # Determine display timezone
        display_tz = "America/New_York"  # Default
        if ctx.triggered:
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if button_id == 'live-tz-berlin-btn':
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
            return empty_fig, "No symbol", "⚠️"
        
        # === CRITICAL LOGGING ===
        logger.info(
            f"source=LIVE_SQLITE symbol={symbol} tf={timeframe} display_tz={display_tz} "
            f"market_tz=America/New_York"
        )
        
        try:
            # === LOAD DATA FROM SQLITE ===
            # Data is returned in America/New_York timezone (market TZ)
            df = live_repo.load_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=500  # Hardcoded limit is OK here (not a business rule)
            )
            
            rows_after_load = len(df)
            
            if df.empty:
                # === EMPTY STATE WITH EXPLANATION ===
                empty_fig = go.Figure()
                empty_fig.add_annotation(
                    text=f"📭 No live data yet for {symbol} {timeframe}<br>" +
                         f"<sub>source: LIVE_SQLITE | rows=0</sub>",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=16)
                )
                
                logger.warning(
                    f"source=LIVE_SQLITE symbol={symbol} tf={timeframe} reason=NO_ROWS "
                    f"rows=0"
                )
                
                return empty_fig, "No data", "🔴"
            
            # === TIMEZONE CONVERSION FOR DISPLAY ===
            # CRITICAL: This MUST NOT change row count
            if display_tz != "America/New_York":
                df.index = df.index.tz_convert(display_tz)
            
            rows_after_tz_conversion = len(df)
            
            # === INVARIANT CHECK ===
            assert rows_after_load == rows_after_tz_conversion, (
                f"TZ conversion changed row count! "
                f"Before: {rows_after_load}, After: {rows_after_tz_conversion}"
            )
            
            # === DROP NaN ROWS (after-hours bars) ===
            rows_before_dropna = len(df)
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            rows_after_dropna = len(df)
            
            if rows_before_dropna > rows_after_dropna:
                logger.debug(
                    f"🧹 Dropped {rows_before_dropna - rows_after_dropna} NaN rows "
                    f"({rows_after_dropna} valid bars remaining)"
                )
            
            # === GET FRESHNESS ===
            freshness = live_repo.get_freshness(symbol, timeframe)
            
            # Calculate badge
            age_minutes = freshness.get('age_minutes')
            if age_minutes is None:
                badge = "🔴"
                fresh_text = "No data"
            elif age_minutes < 5:
                badge = "🟢"
                last_ts = freshness['last_timestamp']
                fresh_text = f"{last_ts.strftime('%H:%M')} ({int(age_minutes)}m ago)"
            elif age_minutes < 30:
                badge = "🟡"
                last_ts = freshness['last_timestamp']
                fresh_text = f"{last_ts.strftime('%H:%M')} ({int(age_minutes)}m ago)"
            else:
                badge = "🔴"
                last_ts = freshness['last_timestamp']
                fresh_text = f"{last_ts.strftime('%H:%M')} ({int(age_minutes)}m ago)"
            
            # === BUILD CHART ===
            config = PriceChartConfig(
                title=f"{symbol} {timeframe} - Live",
                timezone=display_tz,
                show_volume=True,
            )
            
            # Chart builder expects data with timestamp index
            fig = build_price_chart(df, indicators=[], config=config)
            
            # === FINAL LOGGING ===
            first_ts = df.index[0] if len(df) > 0 else None
            last_ts = df.index[-1] if len(df) > 0 else None
            
            logger.info(
                f"source=LIVE_SQLITE symbol={symbol} tf={timeframe} rows={len(df)} "
                f"first_ts={first_ts} last_ts={last_ts} "
                f"market_tz=America/New_York display_tz={display_tz}"
            )
            
            return fig, fresh_text, badge
            
        except Exception as e:
            logger.error(f"Error loading live chart: {e}", exc_info=True)
            
            error_fig = go.Figure()
            error_fig.add_annotation(
                text=f"❌ Error loading {symbol} {timeframe}<br>" +
                     f"<sub>{str(e)[:100]}</sub>",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="red")
            )
            
            return error_fig, "Error", "❌"
    
    
    @app.callback(
        [
            Output("live-tf-m1", "active"),
            Output("live-tf-m5", "active"),
            Output("live-tf-m15", "active"),
        ],
        [
            Input("live-tf-m1", "n_clicks"),
            Input("live-tf-m5", "n_clicks"),
            Input("live-tf-m15", "n_clicks"),
        ]
    )
    def update_timeframe_buttons(m1_clicks, m5_clicks, m15_clicks):
        """Update which timeframe button is active."""
        ctx = callback_context
        if not ctx.triggered:
            return False, True, False  # M5 default
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        return (
            button_id == 'live-tf-m1',
            button_id == 'live-tf-m5',
            button_id == 'live-tf-m15',
        )
    
    
    @app.callback(
        [
            Output("live-tz-ny-btn", "active"),
            Output("live-tz-berlin-btn", "active"),
            Output("live-tz-ny-btn", "outline"),
            Output("live-tz-berlin-btn", "outline"),
        ],
        [
            Input("live-tz-ny-btn", "n_clicks"),
            Input("live-tz-berlin-btn", "n_clicks"),
        ]
    )
    def update_timezone_buttons(ny_clicks, berlin_clicks):
        """Update which timezone button is active."""
        ctx = callback_context
        if not ctx.triggered:
            return True, False, False, True  # NY default (active, not outline)
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'live-tz-ny-btn':
            return True, False, False, True
        else:
            return False, True, True, False
