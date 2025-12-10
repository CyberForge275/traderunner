"""
Active Patterns Callback - Show symbols with active patterns
"""
from dash import Input, Output, html, ALL, no_update
import dash_bootstrap_components as dbc


def register_active_patterns_callback(app):
    """Register callback to show symbols with active patterns."""
    
    @app.callback(
        Output("active-patterns-list", "children"),
        Input("refresh-interval", "n_intervals")
    )
    def update_active_patterns(n_intervals):
        """Show which symbols have active patterns."""
        from ..repositories import get_recent_patterns
        
        # Get patterns from last 24 hours
        patterns = get_recent_patterns(hours=24)
        
        if patterns.empty:
            return html.P("No patterns detected", 
                         className="text-muted", 
                         style={"fontSize": "0.9rem", "marginBottom": "0"})
        
        # Group by symbol and get most recent pattern for each
        symbol_patterns = {}
        for _, row in patterns.iterrows():
            symbol = row['symbol']
            if symbol not in symbol_patterns:
                symbol_patterns[symbol] = row
        
        # Create clickable badges for each symbol with pattern
        badges = []
        for symbol, pattern in symbol_patterns.items():
            side = pattern.get('side', 'BUY')
            color = "success" if side == "BUY" else "danger"
            
            badge = dbc.Button(
                [
                    html.Span(symbol, style={"fontWeight": "bold"}),
                    html.Span(f" {side}", style={"fontSize": "0.8rem", "marginLeft": "4px"})
                ],
                id={"type": "pattern-symbol-badge", "symbol": symbol},
                color=color,
                size="sm",
                className="me-2 mb-2",
                style={"cursor": "pointer"}
            )
            badges.append(badge)
        
        return html.Div(badges, style={"display": "flex", "flexWrap": "wrap"})
    
    @app.callback(
        Output("chart-symbol-selector", "value"),
        Output("chart-data-source-mode", "children"),  # NEW: Set mode
        Input({"type": "pattern-symbol-badge", "symbol": ALL}, "n_clicks"),
        prevent_initial_call=True
    )
    def select_pattern_symbol(n_clicks_list):
        """When pattern badge clicked, select that symbol and set database mode."""
        from dash import ctx
        
        if not ctx.triggered:
            return no_update, no_update
        
        # Get the symbol from the clicked badge
        triggered_id = ctx.triggered_id
        if triggered_id and isinstance(triggered_id, dict):
            return triggered_id['symbol'], "database"  # Set mode to database
        
        return no_update, no_update
