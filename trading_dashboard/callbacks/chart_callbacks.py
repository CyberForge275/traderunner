"""
Chart callback - Updates candlestick chart based on symbol selection
"""
from dash import Input, Output


def register_chart_callbacks(app):
    """Register callbacks for chart interactivity."""
    
    @app.callback(
        Output("candlestick-chart", "figure"),
        Input("chart-symbol-selector", "value"),
        Input("chart-refresh-btn", "n_clicks"),
        Input("tf-m1", "n_clicks"),
        Input("tf-m5", "n_clicks"),
        Input("tf-m15", "n_clicks"),
        Input("tf-h1", "n_clicks"),
        Input("tz-ny-btn", "n_clicks"),
        Input("tz-berlin-btn", "n_clicks"),
        Input("chart-date-picker", "date")
    )
    def update_chart(symbol, refresh_clicks, m1_clicks, m5_clicks, m15_clicks, h1_clicks, ny_clicks, berlin_clicks, selected_date):
        """Update candlestick chart when symbol changes or refresh clicked."""
        from dash import ctx
        from ..repositories.candles import get_candle_data
        from ..repositories import get_recent_patterns
        from ..components.candlestick import create_candlestick_chart
        import pytz
        from datetime import datetime
        
        # Convert selected_date string to date object
        if isinstance(selected_date, str):
            selected_date = datetime.fromisoformat(selected_date).date()
        
        # Determine which timeframe was clicked
        triggered_id = ctx.triggered_id if ctx.triggered else "tf-m5"
        
        timeframe_map = {
            "tf-m1": "M1",
            "tf-m5": "M5",
            "tf-m15": "M15",
            "tf-h1": "H1",
            "chart-symbol-selector": "M5",  # Default when switching symbols
            "chart-refresh-btn": "M5"  # Default when refreshing
        }
        
        timeframe = timeframe_map.get(triggered_id, "M5")
        
        # Determine timezone (default to Berlin)
        if triggered_id == "tz-ny-btn":
            timezone = pytz.timezone("America/New_York")
            tz_label = "NY"
        else:
            timezone = pytz.timezone("Europe/Berlin")
            tz_label = "Berlin"
        
        # Get candle data with selected timeframe and date
        df = get_candle_data(symbol, timeframe=timeframe, hours=24, reference_date=selected_date)
        
        # Check if data is available for selected date
        if df.empty:
            # Create empty chart with message
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_annotation(
                text=f"No stock data streamed on {selected_date}",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="var(--text-secondary)")
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
                height=680
            )
            return fig
        
        # Convert timestamps to selected timezone
        if 'timestamp' in df.columns:
            # Timestamps are already timezone-aware (Berlin by default from mock data)
            # Just convert to the requested timezone
            if df['timestamp'].dt.tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_convert(timezone)
            else:
                # Fallback: if somehow naive, assume Berlin time
                df['timestamp'] = df['timestamp'].dt.tz_localize('Europe/Berlin').dt.tz_convert(timezone)
        
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
        
        # Create chart
        fig = create_candlestick_chart(
            df=df,
            symbol=symbol,
            patterns=patterns,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        # Update chart title with timezone
        fig.update_layout(
            title=dict(
                text=f"{symbol} - {timeframe} ({tz_label} Time)",
                x=0.5,
                xanchor='center'
            )
        )
        
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
