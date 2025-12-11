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
        
        # Check if any live data is available
        available_symbols = check_live_data_availability()
        
        if available_symbols:
            live_class = "status-dot online"
            live_text = "Live data streaming"
            live_count = f"({len(available_symbols)} symbols)"
            
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
                for sym in available_symbols
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
