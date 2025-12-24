"""
Live Data Callback - Display clickable badges for symbols with live data.

Separated from chart callback to avoid circular dependency.
"""
from dash import Input, Output, html
import dash_bootstrap_components as dbc


def register_live_data_callback(app):
    """Register callback to display live data symbols as clickable badges."""
    
    @app.callback(
        Output("live-data-dot", "className"),
        Output("live-data-text", "children"),
        Output("live-data-count", "children"),
        Output("live-symbols-container", "children"),
        Input("refresh-interval", "n_intervals")
    )
    def update_live_data_status(n_intervals):
        """Update live data indicator and clickable symbol badges."""
        from ..repositories.candles import check_live_data_availability
        
        # Check if any live data is available (returns dict)
        availability = check_live_data_availability()
        
        if availability.get('available', False):
            live_class = "status-dot online"
            symbols_list = availability.get('symbols', [])
            symbol_count = availability.get('symbol_count', 0)
            timeframes = availability.get('timeframes', [])
            
            live_text = f"Live ({symbol_count} symbols)"
            live_count = f"Timeframes: {', '.join(timeframes)}"
            
            # Create clickable badges for each symbol
            symbol_badges = [
                dbc.Button(
                    sym,
                    color="success",
                    outline=True,
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
        
        return live_class, live_text, live_count, live_symbols_display
