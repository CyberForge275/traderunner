"""
Pattern Display Component - Shows detected Inside Bar patterns
"""
from dash import html
import pandas as pd


def get_status_class(status: str) -> str:
    """Get CSS class for status badge."""
    status_map = {
        "detected": "status-detected",
        "triggered": "status-triggered",
        "expired": "status-expired",
        "filled": "status-filled",
        "error": "status-error",
        "pending": "status-detected",
        "planned": "status-triggered",
        "sent": "status-filled"
    }
    return status_map.get(status.lower(), "status-detected")


def create_pattern_item(row: dict):
    """Create a single pattern item."""
    symbol = row.get("symbol", "???")
    detected_at = row.get("detected_at", "")
    status = row.get("status", "detected")
    side = row.get("side", "BUY")
    entry = row.get("entry_price", 0.0)
    
    side_color = "var(--accent-green)" if side == "BUY" else "var(--accent-red)"
    
    return html.Div(
        className="order-flow-item",
        children=[
            html.Div(
                className="order-flow-icon",
                style={"backgroundColor": side_color},
                children=[html.Span(side[0], style={"color": "white", "fontWeight": "bold"})]
            ),
            html.Div([
                html.Div([
                    html.Strong(symbol),
                    html.Span(f" @ ${entry:.2f}" if entry else "", style={"color": "var(--text-secondary)"})
                ]),
                html.Small(detected_at, style={"color": "var(--text-secondary)"})
            ], style={"flex": 1}),
            html.Span(status.upper(), className=f"status-badge {get_status_class(status)}")
        ]
    )


def create_patterns_panel(patterns_df: pd.DataFrame):
    """Create the patterns display panel."""
    if patterns_df.empty:
        items = [html.P("No patterns detected", className="text-muted", style={"padding": "20px"})]
    else:
        items = [create_pattern_item(row) for _, row in patterns_df.head(10).iterrows()]
    
    return html.Div(
        className="dashboard-card",
        children=[
            html.H5("Active Patterns"),
            html.Div(items)
        ]
    )
