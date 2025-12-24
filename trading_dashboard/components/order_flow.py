"""
Order Flow Component - Shows order processing pipeline
"""
from dash import html
import pandas as pd


def create_order_item(row: dict):
    """Create a single order flow item."""
    symbol = row.get("symbol", "???")
    side = row.get("side", "BUY")
    quantity = row.get("quantity", 0)
    price = row.get("price", 0.0)
    status = row.get("status", "pending")
    created_at = row.get("created_at", "")

    status_map = {
        "pending": ("⏳", "status-detected"),
        "planned": ("📋", "status-triggered"),
        "sending": ("🚀", "status-filled"),
        "sent": ("✈️", "status-filled"),
        "filled": ("✅", "status-filled"),
        "error": ("❌", "status-error"),
        "rejected": ("🚫", "status-error")
    }

    icon, status_class = status_map.get(status.lower(), ("❓", "status-detected"))

    return html.Div(
        className="order-flow-item",
        children=[
            html.Span(icon, style={"fontSize": "1.5rem", "marginRight": "12px"}),
            html.Div([
                html.Div([
                    html.Strong(f"{side} {symbol}"),
                    html.Span(f" x{quantity} @ ${price:.2f}", style={"color": "var(--text-secondary)"})
                ]),
                html.Small(created_at, style={"color": "var(--text-secondary)"})
            ], style={"flex": 1}),
            html.Span(status.upper(), className=f"status-badge {status_class}")
        ]
    )


def create_order_flow_panel(orders_df: pd.DataFrame):
    """Create the order flow display panel."""
    if orders_df.empty:
        items = [html.P("No orders today", className="text-muted", style={"padding": "20px"})]
    else:
        items = [create_order_item(row) for _, row in orders_df.head(10).iterrows()]

    return html.Div(
        className="dashboard-card",
        children=[
            html.H5("Order Flow"),
            html.Div(items)
        ]
    )
