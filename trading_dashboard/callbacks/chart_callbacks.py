"""
Chart callback - Updates candlestick chart based on symbol selection

REFACTORED: Uses visualization layer builder pattern.
No direct Plotly imports - all chart building delegated to visualization/plotly/.
"""
from dash import Input, Output, State
import pandas as pd
import logging

# Import visualization layer (clean separation)
from visualization.plotly import build_price_chart, PriceChartConfig

logger = logging.getLogger(__name__)


def _determine_session_mode(include_pre: bool, include_after: bool) -> str:
    """
    Convert session toggles to SessionMode enum value.
    
    Args:
        include_pre: Include pre-market hours
        include_after: Include after-hours hours
    
    Returns:
        SessionMode string: "all", "rth", "premarket_rth", "rth_afterhours", "all_extended"
    """
    if include_pre and include_after:
        return "all_extended"  # 4:00-20:00 ET
    elif include_pre:
        return "premarket_rth"  # 4:00-16:00 ET
    elif include_after:
        return "rth_afterhours"  # 9:30-20:00 ET
    else:
        return "rth"  # 9:30-16:00 ET


def register_chart_callbacks(app):
    """Register callbacks for chart interactivity."""
    
    @app.callback(
        Output("indicator-toggles", "options"),
        Input("indicator-strategy-selector", "value")
    )
    def update_indicator_options(strategy_name):
        """Update indicator toggle options based on selected strategy."""
        from ..services.strategy_indicators import get_available_indicators
        
        if strategy_name == "none" or not strategy_name:
            return []  # Empty options
        
        # Get available indicators for this strategy
        available = get_available_indicators(strategy_name)
        
        if not available:
            return []
        
        # Return options for checklist
        return [
            {"label": f" {ind.replace('_', ' ').upper()}", "value": ind}
            for ind in available
        ]
    
    @app.callback(
        Output("candlestick-chart", "figure"),
        Input("chart-symbol-selector", "value"),
        Input("chart-refresh-btn", "n_clicks"),
        Input("tf-m1", "n_clicks"),
        Input("tf-m5", "n_clicks"),
        Input("tf-m15", "n_clicks"),
        Input("tf-h1", "n_clicks"),
        Input("tf-d1", "n_clicks"),  # NEW: D1 daily timeframe
        Input("tz-ny-btn", "n_clicks"),
        Input("tz-berlin-btn", "n_clicks"),
        Input("chart-date-picker", "date"),
        Input("market-session-toggles", "value"),
        Input("indicator-strategy-selector", "value"),
        State("indicator-toggles", "value"),  # Changed to State - prevents initial error
        State("chart-data-source-mode", "children"),
        State("d1-day-range", "value")  # NEW: Configurable day range for D1
    )
    def update_chart(
        symbol, refresh_clicks, m1_clicks, m5_clicks, m15_clicks, h1_clicks, d1_clicks,
        ny_clicks, berlin_clicks, selected_date, session_toggles,
        indicator_strategy, indicator_toggles, data_source_mode, d1_day_range
    ):
        """
        Update candlestick chart - orchestrates data fetching and chart building.
        
        This callback:
        1. Fetches OHLCV data from repositories (domain layer)
        2. Computes indicators if needed
        3. Builds chart config
        4. Calls visualization layer to build chart
        5. Returns figure + live data status
        """
        from dash import ctx
        from ..repositories.candles import (
            get_candle_data,
            get_live_candle_data,
            get_live_symbols_today
        )
        import dash_bootstrap_components as dbc
        from dash import html
        from datetime import datetime
        import pytz
        
        # Convert selected_date string to date object
        if isinstance(selected_date, str):
            selected_date = datetime.fromisoformat(selected_date).date()
        
        # Determine which input triggered the callback
        triggered_id = ctx.triggered_id if ctx.triggered else None
        
        # === 1. Determine timeframe ===
        timeframe_map = {
            "tf-m1": "M1",
            "tf-m15": "M15",
            "tf-h1": "H1",
            "tf-d1": "D1",  # NEW: Daily timeframe
        }
        timeframe = timeframe_map.get(triggered_id, "M5")  # Default M5
        
        # === 2. Determine timezone ===
        if triggered_id == "tz-ny-btn":
            timezone = pytz.timezone("America/New_York")
            tz_label = "NY"
        else:
            timezone = pytz.timezone("Europe/Berlin")
            tz_label = "Berlin"
        
        # === 3. Check live data availability (for status indicator) ===
        availability = check_live_data_availability(selected_date)
        
        if availability['available']:
            live_class = "status-dot online"
            symbol_count = availability['symbol_count']
            symbols_list = availability.get('symbols', [])
            timeframes = ', '.join(availability['timeframes'])
            live_text = f"Live ({symbol_count} symbols)"
            live_count = f"Timeframes: {timeframes}"
            
            # Clickable symbol badges
            symbol_badges = [
                dbc.Button(
                    sym,
                    color="success",
                    size="sm",
                    className="me-2 mb-2",
                    style={
                        "cursor": "pointer",
                        "fontSize": "0.85rem",
                        "padding": "0.35rem 0.65rem"
                    },
                    id={"type": "live-symbol-badge", "symbol": sym}
                )
                for sym in symbols_list
            ]
            live_symbols_display = html.Div(
                symbol_badges,
                style={"display": "flex", "flexWrap": "wrap", "gap": "5px"}
            )
        else:
            live_class = "status-dot offline"
            live_text = "No live data"
            live_count = ""
            live_symbols_display = None
        
        # === 4. Fetch OHLCV data (domain layer) ===
        # Determine data source mode based on trigger
        logger.info(f"📍 Triggered by: {triggered_id}, Current mode: {data_source_mode}")
        
        # Timeframe button clicks should use parquet for symbol selector mode
        # Badge clicks should use database for Active Patterns mode
        timeframe_triggers = {'tf-m1', 'tf-m5', 'tf-m15', 'tf-h1', 'tf-d1'}
        
        if triggered_id in timeframe_triggers or triggered_id == 'chart-symbol-selector':
            # User clicked timeframe or selected symbol → use parquet (symbol selector mode)
            new_mode = "parquet"
            logger.info(f"   → Timeframe/Symbol selector clicked → PARQUET mode")
        elif data_source_mode == "database":
            # Badge explicitly set database mode → keep it (Active Patterns mode)
            new_mode = "database"
            logger.info(f"   → Active Patterns badge mode → DATABASE mode")
        else:
            # Default to parquet
            new_mode = "parquet"
            logger.info(f"   → Default → PARQUET mode")
        
        logger.info(f"   Final: source={new_mode}, trigger={triggered_id}, tf={timeframe}")
        
        if new_mode == "database":
            # Active Patterns mode: load from websocket database
            logger.info(f"   → Loading from DATABASE for {symbol}")
            df = get_live_candle_data(symbol, timeframe, selected_date, limit=500)
        else:
            # Symbol selector mode: load from parquet files
            logger.info(f"   → Loading from PARQUET for {symbol}")
            
            # Use days_back for D1, hours for other timeframes
            if timeframe == "D1":
                logger.info(f"🔍 CHART CALLBACK: D1 timeframe selected")
                logger.info(f"   Symbol: {symbol}")
                logger.info(f"   Days range: {d1_day_range or 180}")
                logger.info(f"   Reference date: {selected_date}")
                
                df = get_candle_data(
                    symbol,
                    timeframe=timeframe,
                    days_back=d1_day_range or 180,  # Use UI selection or default
                    reference_date=selected_date
                )
                
                logger.info(f"🔍 CHART CALLBACK: After get_candle_data")
                logger.info(f"   DataFrame shape: {df.shape if not df.empty else 'EMPTY'}")
                if not df.empty:
                    logger.info(f"   Columns: {list(df.columns)}")
                    logger.info(f"   Index: {df.index[:3].tolist() if len(df) > 0 else 'N/A'}")
            else:
                df = get_candle_data(
                    symbol,
                    timeframe=timeframe,
                    hours=24,
                    reference_date=selected_date
                )
        
        # === 5. Handle empty data early ===
        if df.empty:
            logger.warning(f"⚠️  No data for {symbol} on {selected_date}")
            
            # Use builder to create empty chart
            config = PriceChartConfig(
                title=f"{symbol} - {timeframe} ({tz_label} Time)",
                show_volume=False,
                height=680,
            )
            # Empty DataFrame with required columns
            empty_df = pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"]
            )
            fig = build_price_chart(empty_df, {}, config)
            
            # Add custom annotation for no data message
            fig.add_annotation(
                text="📊",
                xref="paper", yref="paper",
                x=0.5, y=0.6,
                showarrow=False,
                font=dict(size=80)
            )
            fig.add_annotation(
                text=f"No stock data available for {symbol} on {selected_date}",
                xref="paper", yref="paper",
                x=0.5, y=0.45,
                showarrow=False,
                font=dict(size=18)
            )
            
            return fig
        
        # === 6. Prepare data: Convert to DataFrame with datetime index ===
        if 'timestamp' in df.columns:
            # Convert to requested timezone
            # Note: Parquet data is stored in Berlin time by default
            if df['timestamp'].dt.tz is None:
                # Localize naive timestamps as Berlin time (source timezone)
                df['timestamp'] = df['timestamp'].dt.tz_localize('Europe/Berlin')
            
            # Now convert to the requested display timezone
            df['timestamp'] = df['timestamp'].dt.tz_convert(timezone)
            
            # Set as index for builder
            ohlcv = df.set_index('timestamp')[['open', 'high', 'low', 'close', 'volume']]
        else:
            # Fallback if no timestamp column
            ohlcv = df[['open', 'high', 'low', 'close', 'volume']]
        
        # === 7. Apply session filtering for indicator computation ===
        # We need to filter data BEFORE computing indicators, but builder also filters
        # So we do it here inline to avoid importing private functions
        include_pre = 'pre' in (session_toggles or [])
        include_after = 'after' in (session_toggles or [])
        session_mode = _determine_session_mode(include_pre, include_after)
        
        # Filter data for indicator computation (inline, not importing private _filter_session)
        if session_mode == "all":
            ohlcv_for_indicators = ohlcv
        else:
            # Simple inline filtering logic
            import pytz
            ny_tz = pytz.timezone('America/New_York')
            
            # Convert to NY time for filtering
            df_temp = ohlcv.copy()
            if df_temp.index.tz is None:
                df_temp.index = df_temp.index.tz_localize('UTC')
            df_temp.index = df_temp.index.tz_convert(ny_tz)
            
            hour = df_temp.index.hour
            minute = df_temp.index.minute
            
            if session_mode == "rth":
                mask = ((hour == 9) & (minute >= 30)) | ((hour >= 10) & (hour < 16))
            elif session_mode == "premarket_rth":
                mask = (hour >= 4) & (hour < 16)
            elif session_mode == "rth_afterhours":
                mask = ((hour == 9) & (minute >= 30)) | ((hour >= 10) & (hour < 20))
            elif session_mode == "all_extended":
                mask = (hour >= 4) & (hour < 20)
            else:
                mask = pd.Series([True] * len(ohlcv), index=ohlcv.index)
            
            ohlcv_for_indicators = ohlcv[mask]
        
        logger.info(f"📊 Session filter for indicators: {session_mode} ({len(ohlcv)} → {len(ohlcv_for_indicators)} bars)")
        
        # === 8. Compute indicators on FILTERED data ===
        from ..services.strategy_indicators import compute_strategy_indicators
        
        indicators = {}
        
        # Compute strategy indicators if selected
        if indicator_strategy and indicator_strategy != "none" and indicator_toggles:
            try:
                indicators = compute_strategy_indicators(
                    indicator_strategy,
                    ohlcv_for_indicators,  # Use filtered data!
                    indicator_toggles
                )
                logger.info(f"🎨 Computed {len(indicators)} indicators: {list(indicators.keys())}")
            except Exception as e:
                logger.error(f"Error computing indicators: {e}")
                # Continue without indicators
        
        # === 9. Build chart configuration ===
        # IMPORTANT: Daily data (D1) has no session concept - always show all data
        chart_session_mode = "all" if timeframe == "D1" else session_mode
        
        # Builder will do its own filtering
        config = PriceChartConfig(
            show_volume=True,
            show_grid=True,
            show_rangeslider=False,
            session_mode=chart_session_mode,  # Use 'all' for daily data
            theme_mode="dark",
            title=f"{symbol} - {timeframe} ({tz_label} Time)",
            height=680,
        )
        
        # === 10. Build chart (visualization layer) ===
        logger.info(f"🎨 Building chart with config: {config.session_mode}, volume={config.show_volume}")
        fig = build_price_chart(ohlcv, indicators, config)  # Builder filters OHLCV
        
        # === 10. Pattern overlays (future enhancement) ===
        # TODO: Add pattern markers from get_recent_patterns()
        # This would be added as annotations after builder returns
        
        return fig
    
    @app.callback(
        Output("pattern-details", "children"),
        Input("chart-symbol-selector", "value")
    )
    def update_pattern_info(symbol):
        """Update pattern details panel."""
        from dash import html
        from ..repositories import get_recent_patterns
        
        patterns = get_recent_patterns(hours=24)
        if patterns.empty:
            return [html.P("No patterns detected", className="text-muted")]
        
        patterns = patterns[patterns['symbol'] == symbol]
        if patterns.empty:
            return [html.P(f"No patterns for {symbol}", className="text-muted")]
        
        latest = patterns.iloc[0]
        
        return [
            html.Div([
                html.Strong("Status: "),
                html.Span(
                    latest.get('status', 'N/A').upper(),
                    className=f"status-badge status-{latest.get('status', 'detected')}"
                )
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Strong("Side: "),
                html.Span(latest.get('side', 'N/A'))
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Strong("Entry: "),
                html.Span(f"${latest.get('entry_price', 0):.2f}")
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Strong("Stop Loss: "),
                html.Span(
                    f"${latest.get('stop_loss', 0):.2f}",
                    style={"color": "var(--accent-red)"}
                )
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Strong("Take Profit: "),
                html.Span(
                    f"${latest.get('take_profit', 0):.2f}",
                    style={"color": "var(--accent-green)"}
                )
            ])
        ]
