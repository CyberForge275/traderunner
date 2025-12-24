"""
Live Monitor Layout - Main dashboard view
"""
from dash import html
import dash_bootstrap_components as dbc

from ..components import create_watchlist, create_patterns_panel, create_order_flow_panel
from ..repositories import get_watchlist_symbols, get_recent_patterns, get_order_intents, get_system_status, get_portfolio_summary


def create_status_indicator(label: str, is_online: bool):
    """Create a status indicator with label."""
    status_class = "online" if is_online else "offline"
    return html.Div([
        html.Span(className=f"status-indicator {status_class}"),
        html.Span(label)
    ], style={"marginBottom": "8px"})


def create_portfolio_card(portfolio: dict):
    """Create the portfolio value card."""
    pnl = portfolio.get("daily_pnl", 0)
    pnl_pct = portfolio.get("daily_pnl_pct", 0)
    pnl_class = "pnl-positive" if pnl >= 0 else "pnl-negative"
    pnl_sign = "+" if pnl >= 0 else ""

    return html.Div(
        className="dashboard-card",
        children=[
            html.H5("Portfolio Value"),
            html.Div(
                f"${portfolio.get('total_value', 0):,.2f}",
                className="portfolio-value"
            ),
            html.Div([
                html.Span(
                    f"{pnl_sign}${abs(pnl):,.2f} ({pnl_sign}{pnl_pct:.2f}%)",
                    className=pnl_class
                ),
                html.Span(" today", style={"color": "var(--text-secondary)"})
            ])
        ]
    )


def create_system_status_card(status: dict):
    """Create system status card."""
    return html.Div(
        className="dashboard-card",
        children=[
            html.H5("System Status"),
            create_status_indicator("Market Data Stream", status.get("marketdata_stream", False)),
            create_status_indicator("Trader API", status.get("automatictrader_api", False)),
            create_status_indicator("Trader Worker", status.get("automatictrader_worker", False)),
            create_status_indicator("Signals DB", status.get("signals_db", False)),
            create_status_indicator("Trading DB", status.get("trading_db", False))
        ]
    )


def create_live_monitor_layout():
    """Create the Live Monitor tab layout."""
    symbols = get_watchlist_symbols()
    patterns = get_recent_patterns(hours=24)
    orders = get_order_intents(hours=24)
    system_status = get_system_status()
    portfolio = get_portfolio_summary()

    return html.Div([
        dbc.Row([
            # Left: Watchlist
            dbc.Col([
                create_watchlist(symbols),
            ], width=3),

            # Center: Patterns + Orders
            dbc.Col([
                create_patterns_panel(patterns),
                create_order_flow_panel(orders)
            ], width=6),

            # Right: Portfolio + Status
            dbc.Col([
                create_portfolio_card(portfolio),
                create_system_status_card(system_status)
            ], width=3)
        ])
    ], style={"padding": "20px"})


# Callback-friendly version that returns updatable content
def get_live_monitor_content():
    """Get live monitor content for callbacks."""
    return create_live_monitor_layout()
