"""
Watchlist Component - Displays strategy symbols with current prices
"""
from dash import html


def create_watchlist_item(symbol: str, price: float = 0.0, change_pct: float = 0.0):
    """Create a single watchlist item."""
    change_class = "price-up" if change_pct >= 0 else "price-down"
    change_sign = "+" if change_pct >= 0 else ""
    
    return html.Div(
        className="watchlist-item",
        children=[
            html.Div([
                html.Span(symbol, className="symbol-name"),
            ]),
            html.Div([
                html.Span(f"${price:.2f}", style={"marginRight": "8px"}),
                html.Span(
                    f"{change_sign}{change_pct:.2f}%",
                    className=change_class
                )
            ])
        ]
    )


def create_watchlist(symbols: list[str], prices: dict = None):
    """Create the watchlist component."""
    if prices is None:
        prices = {}
    
    items = []
    for symbol in symbols:
        price_data = prices.get(symbol, {"price": 0.0, "change_pct": 0.0})
        items.append(create_watchlist_item(
            symbol,
            price_data.get("price", 0.0),
            price_data.get("change_pct", 0.0)
        ))
    
    return html.Div(
        className="dashboard-card",
        children=[
            html.H5("Watchlist"),
            html.Div(items) if items else html.P("No symbols configured", className="text-muted")
        ]
    )
