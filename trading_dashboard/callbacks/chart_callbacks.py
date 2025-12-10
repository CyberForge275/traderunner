"""
Chart callback - Updates candlestick chart based on symbol selection
"""
from dash import Input, Output, State
import pandas as pd


def filter_market_hours(df, include_pre, include_after, timezone):
    """
    Filter dataframe to include only selected market sessions.
    
    US Market Hours (ET/EST):
    - Pre-Market: 4:00 AM - 9:30 AM
    - Regular: 9:30 AM - 4:00 PM (always included)
    - After-Hours: 4:00 PM - 8:00 PM
    
    Args:
        df: DataFrame with timestamp column
        include_pre: bool, include pre-market data
        include_after: bool, include after-hours data
        timezone: pytz timezone object for display
        
    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df
    
    # Work in ET timezone for filtering
    import pytz
    et_tz = pytz.timezone('America/New_York')
    
    # Convert to ET if needed
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
    df_et = df.copy()
    df_et['timestamp'] = df_et['timestamp'].dt.tz_convert(et_tz)
    
    # Extract hour and minute in ET
    hour = df_et['timestamp'].dt.hour
    minute = df_et['timestamp'].dt.minute
    
    # Define session masks
    # Regular hours: 9:30 AM - 4:00 PM (always included)
    regular = ((hour == 9) & (minute >= 30)) | ((hour >= 10) & (hour < 16))
    
    # Pre-market: 4:00 AM - 9:30 AM
    pre_market = (hour >= 4) & ((hour < 9) | ((hour == 9) & (minute < 30)))
    
    # After-hours: 4:00 PM - 8:00 PM
    after_hours = (hour >= 16) & (hour < 20)
    
    # Build filter mask
    mask = regular  # Always include regular hours
    if include_pre:
        mask = mask | pre_market
    if include_after:
        mask = mask | after_hours
    
    return df[mask]


def register_chart_callbacks(app):
    """Register callbacks for chart interactivity."""
    
    @app.callback(
        Output("candlestick-chart", "figure"),
        Output("live-data-dot", "className"),
        Output("live-data-text", "children"),
        Output("live-data-count", "children"),
        Output("live-symbols-container", "children"),  # Clickable symbols
        # NOTE: Do NOT output to chart-data-source-mode here - Active Patterns callback owns it
        Input("chart-symbol-selector", "value"),
        Input("chart-refresh-btn", "n_clicks"),
        Input("tf-m1", "n_clicks"),  # Fixed: was timeframe-M1-btn
        Input("tf-m5", "n_clicks"),  # Fixed: was timeframe-M5-btn
        Input("tf-m15", "n_clicks"),  # Fixed: was timeframe-M15-btn
        Input("tf-h1", "n_clicks"),  # Fixed: was timeframe-H1-btn
        Input("tz-ny-btn", "n_clicks"),
        Input("tz-berlin-btn", "n_clicks"),
        Input("chart-date-picker", "date"),  # Fixed: was selected-date
        Input("market-session-toggles", "value"),
        State("chart-data-source-mode", "children")  # Read current mode
    )
    def update_chart(symbol, refresh_clicks, m1_clicks, m5_clicks, m15_clicks, h1_clicks, ny_clicks, berlin_clicks, selected_date, session_toggles, data_source_mode):
        """Update candlestick chart when symbol changes or refresh clicked."""
        from dash import ctx
        from ..repositories.candles import get_candle_data, get_live_candle_data
        from ..repositories import get_recent_patterns
        from ..components.candlestick import create_candlestick_chart
        import pytz
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"📅 update_chart called with selected_date RAW: {selected_date}, type: {type(selected_date)}")
        
        # Convert selected_date string to date object
        if isinstance(selected_date, str):
            selected_date = datetime.fromisoformat(selected_date).date()
            logger.info(f"📅 Converted to date object: {selected_date}")
        
        # Determine which timeframe button was clicked
        triggered_id = ctx.triggered_id if ctx.triggered else None
        
        if triggered_id == "tf-m1":
            timeframe = "M1"
        elif triggered_id == "tf-m15":
            timeframe = "M15"
        elif triggered_id == "tf-h1":
            timeframe = "H1"
        else:
            timeframe = "M5"  # Default
        
        # Determine timezone (default to Berlin)
        if triggered_id == "tz-ny-btn":
            timezone = pytz.timezone("America/New_York")
            tz_label = "NY"
        else:
            timezone = pytz.timezone("Europe/Berlin")
            tz_label = "Berlin"
        
        # ====================================================================
        # CRITICAL: Check live data availability FIRST, before parquet data
        # This ensures the status is always checked, even if parquet is empty
        # ==================================================================
        from ..repositories.candles import check_live_data_availability
        availability = check_live_data_availability(selected_date)
        
        # LOG RESULTS
        logger.info(f"🔍 Live data availability result: {availability}")
        
        # Determine live data status (fast, no candle loading)
        if availability['available']:
            live_class = "status-dot online"
            symbol_count = availability['symbol_count']
            symbols_list = availability.get('symbols', [])
            timeframes = ', '.join(availability['timeframes'])
            live_text = f"Live ({symbol_count} symbols)"
            # Show symbol names and timeframes
            live_count = f"Timeframes: {timeframes}"
            
            # Create clickable symbol badges
            import dash_bootstrap_components as dbc
            from dash import html
            symbol_badges = [
                dbc.Badge(
                    sym,
                    href=f"?symbol={sym}",
                    color="success",
                    className="me-1 mb-1",
                    style={
                        "cursor": "pointer",
                        "fontSize": "0.85rem",
                        "padding": "0.35rem 0.65rem"
                    },
                    id={"type": "live-symbol-badge", "symbol": sym}
                )
                for sym in symbols_list
            ]
            live_symbols_display = html.Div(symbol_badges, style={"display": "flex", "flexWrap": "wrap", "gap": "5px"})
            
            logger.info(f"✅ Setting status to ONLINE: {live_text}")
        else:
            live_class = "status-dot offline"
            live_text = "No live data"
            live_count = ""
            live_symbols_display = None
            logger.warning(f"❌ Setting status to OFFLINE")
        
        # Determine which input triggered callback
        triggered_id = ctx.triggered_id if ctx.triggered else None
        
        # If Symbol dropdown changed, reset to parquet mode
        new_mode = data_source_mode  # Default: keep current mode
        if triggered_id == "chart-symbol-selector":
            new_mode = "parquet"  # Dropdown always uses parquet
        
        logger.info(f"📊 Data source mode: {new_mode} (triggered by: {triggered_id})")
        
        # Load data based on mode
        if new_mode == "database":
            # Active Patterns mode: load from websocket database
            logger.info(f"   → Loading from DATABASE (market_data.db) for {symbol}")
            from ..repositories.candles import get_live_candle_data
            df = get_live_candle_data(symbol, timeframe, selected_date, limit=500)
        else:
            # Symbol selector mode: load from parquet files
            logger.info(f"   → Loading from PARQUET files for {symbol}")
            from ..repositories.candles import get_candle_data
            df = get_candle_data(symbol, timeframe=timeframe, hours=24, reference_date=selected_date)
        
        # Check if data is available for selected date
        if df.empty:
            # Create empty chart with helpful message
            import plotly.graph_objects as go
            fig = go.Figure()
            
            # Add large icon and message
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
                font=dict(size=18, color="#E0E0E0")
            )
            
            fig.add_annotation(
                text="Data files contain historical data from November 26, 2024.<br>Please select an earlier date or wait for new data to be streamed.",
                xref="paper", yref="paper",
                x=0.5, y=0.35,
                showarrow=False,
                font=dict(size=14, color="#A0A0A0")
            )
            
            fig.update_layout(
                template="plotly_dark",
                title=dict(
                    text=f"{symbol} - {timeframe} ({tz_label} Time)",
                    x=0.5,
                    xanchor='center'
                ),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=680,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            # FIXED: Return with live data status from check above, not hardcoded offline
            return fig, live_class, live_text, live_count, live_symbols_display
        
        # Convert timestamps to selected timezone
        if 'timestamp' in df.columns:
            # Timestamps are already timezone-aware (Berlin by default from mock data)
            # Just convert to the requested timezone
            if df['timestamp'].dt.tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_convert(timezone)
            else:
                # Fallback: if somehow naive, assume Berlin time
                df['timestamp'] = df['timestamp'].dt.tz_localize('Europe/Berlin').dt.tz_convert(timezone)
        
        # Apply market session filtering
        include_pre = 'pre' in (session_toggles or [])
        include_after = 'after' in (session_toggles or [])
        df = filter_market_hours(df, include_pre, include_after, timezone)
        
        # Check if filtering removed all data
        if df.empty:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_annotation(
                text="📊",
                xref="paper", yref="paper",
                x=0.5, y=0.6,
                showarrow=False,
                font=dict(size=80)
            )
            fig.add_annotation(
                text=f"No data in selected market sessions",
                xref="paper", yref="paper",
                x=0.5, y=0.45,
                showarrow=False,
                font=dict(size=18, color="#E0E0E0")
            )
            fig.add_annotation(
                text="Try enabling Pre-Market or After-Hours sessions",
                xref="paper", yref="paper",
                x=0.5, y=0.35,
                showarrow=False,
                font=dict(size=14, color="#A0A0A0")
            )
            fig.update_layout(
                template="plotly_dark",
                title=dict(
                    text=f"{symbol} - {timeframe} ({tz_label} Time)",
                    x=0.5,
                    xanchor='center'
                ),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=680,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            return fig, "status-dot offline", "No live data", ""
        
        # Get patterns for this symbol
        patterns = get_recent_patterns(hours=24)
        if not patterns.empty:
            patterns = patterns[patterns['symbol'] == symbol]
        
        # Get latest pattern info for order levels
        entry_price = None
        stop_loss = None
        take_profit = None
        
        if not patterns.empty:
            latest = patterns.iloc[0]
            entry_price = latest.get('entry_price')
            stop_loss = latest.get('stop_loss')
            take_profit = latest.get('take_profit')
        
        # OPTIMIZED: Fast availability check instead of loading all candles
        from ..repositories.candles import check_live_data_availability
        availability = check_live_data_availability(selected_date)
        
        # LOG RESULTS
        logger.info(f"🔍 Live data availability result: {availability}")
        
        # Determine live data status (fast, no candle loading)
        if availability['available']:
            live_class = "status-dot online"
            symbol_count = availability['symbol_count']
            timeframes = ', '.join(availability['timeframes'])
            live_text = f"Live ({symbol_count} symbols)"
            logger.info(f"✅ Setting status to ONLINE: {live_text}")
            live_count = f"Timeframes: {timeframes}"
        else:
            live_class = "status-dot offline"
            live_text = "No live data"
            live_count = ""
            logger.warning(f"❌ Setting status to OFFLINE")
        
        # Note: Adapter already handles live data for today's date
        # No need for separate live candle loading
        df_live = None  # Reserved for future overlay feature (live on top of historic)
        
        # Create chart with both parquet and live data
        fig = create_candlestick_chart(
            df=df,
            symbol=symbol,
            patterns=patterns,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            df_live=df_live  # Pass live data for overlay
        )
        
        # Update chart title with timezone
        fig.update_layout(
            title=dict(
                text=f"{symbol} - {timeframe} ({tz_label} Time)",
                x=0.5,
                xanchor='center'
            )
        )
        
        return fig, live_class, live_text, live_count, live_symbols_display
    
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
                html.Span(latest.get('status', 'N/A').upper(), 
                         className=f"status-badge status-{latest.get('status', 'detected')}")
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
                html.Span(f"${latest.get('stop_loss', 0):.2f}", style={"color": "var(--accent-red)"})
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Strong("Take Profit: "),
                html.Span(f"${latest.get('take_profit', 0):.2f}", style={"color": "var(--accent-green)"})
            ])
        ]
