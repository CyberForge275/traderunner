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
from trading_dashboard.utils.chart_preprocess import preprocess_for_chart
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
            
            # === LOG METADATA ===
            logger.info(f"chart_meta {meta}")
            
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
            config = PriceChartConfig(
                title=f"{symbol} {timeframe_str} - Backtesting",
                timezone=display_tz,
                show_volume=True,
            )
            
            fig = build_price_chart(df_processed, indicators=[], config=config)
            
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
