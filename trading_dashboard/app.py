#!/usr/bin/env python3
"""
Automatic Trading Factory Dashboard
Real-time monitoring for trading signals, orders, and portfolio
"""
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
from datetime import datetime

from trading_dashboard.config import PORT, HOST, DEBUG, UPDATE_INTERVAL_MS
from trading_dashboard.auth import add_auth_to_app
from trading_dashboard.layouts import (
    get_live_monitor_content,
    get_charts_content,
    get_portfolio_content,
    get_history_content
)
from trading_dashboard.callbacks.chart_callbacks import register_chart_callbacks
from trading_dashboard.callbacks.timeframe_callbacks import register_timeframe_callbacks
from trading_dashboard.callbacks.timezone_callbacks import register_timezone_callbacks
from trading_dashboard.callbacks.history_callbacks import register_history_callbacks
from trading_dashboard.callbacks.active_patterns_callback import register_active_patterns_callback


# Initialize Dash app with dark theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    title="Trading Dashboard",
    update_title="Updating..."
)

# Add authentication
add_auth_to_app(app)

# App layout
app.layout = html.Div([
    # Header
    html.Div(
        className="dashboard-header",
        children=[
            html.Div([
                html.Span("⚡", style={"fontSize": "1.5rem", "marginRight": "8px"}),
                html.Span("Automatic Trading Factory", className="dashboard-title")
            ]),
            html.Div(id="header-time", style={"color": "var(--text-secondary)"})
        ]
    ),
    
    # Navigation Tabs
    dbc.Tabs(
        id="main-tabs",
        active_tab="live-monitor",
        children=[
            dbc.Tab(label="Live Monitor", tab_id="live-monitor"),
            dbc.Tab(label="Portfolio", tab_id="portfolio"),
            dbc.Tab(label="Charts", tab_id="charts"),
            dbc.Tab(label="History", tab_id="history"),
        ],
        style={"backgroundColor": "var(--bg-secondary)"}
    ),
    
    # Tab content
    html.Div(id="tab-content", style={"paddingBottom": "50px"}),
    
    # Auto-refresh interval (only for Live Monitor tab)
    dcc.Interval(
        id="refresh-interval",
        interval=UPDATE_INTERVAL_MS,
        n_intervals=0,
        disabled=False  # Will be controlled by tab switching
    ),
    
    # Status bar
    html.Div(
        className="status-bar",
        children=[
            html.Span("🟢 Connected", style={"marginRight": "24px"}),
            html.Span(id="last-update", children="Last update: --"),
            html.Span(" | Market: ", style={"marginLeft": "24px"}),
            html.Span(id="market-status", children="Checking...")
        ]
    )
])


@app.callback(
    Output("tab-content", "children"),
    Output("header-time", "children"),
    Output("last-update", "children"),
    Input("main-tabs", "active_tab"),
    Input("refresh-interval", "n_intervals")
)
def update_content(active_tab, n_intervals):
    """Update tab content and timestamps."""
    from dash import ctx
    
    now = datetime.now()
    time_str = now.strftime("%H:%M:%S")
    update_str = f"Last update: {time_str}"
    
    # Check what triggered this callback
    triggered_id = ctx.triggered_id if ctx.triggered else None
    
    # For Charts tab, ONLY update when tab is switched, NOT on interval
    if active_tab == "charts" and triggered_id == "refresh-interval":
        # Don't update - return current content without re-rendering
        from dash import no_update
        return no_update, time_str, update_str
    
    if active_tab == "live-monitor":
        content = get_live_monitor_content()
    elif active_tab == "portfolio":
        content = get_portfolio_content()
    elif active_tab == "charts":
        content = get_charts_content()
    elif active_tab == "history":
        content = get_history_content()
    else:
        content = html.Div("Unknown tab")
    
    return content, time_str, update_str


@app.callback(
    Output("refresh-interval", "disabled"),
    Input("main-tabs", "active_tab")
)
def control_refresh_interval(active_tab):
    """Enable refresh interval only on Live Monitor tab."""
    # Only auto-refresh on live-monitor tab
    return active_tab != "live-monitor"


# Register chart callbacks
register_chart_callbacks(app)
register_timeframe_callbacks(app)
register_timezone_callbacks(app)
register_history_callbacks(app)
register_active_patterns_callback(app)


@app.callback(
    Output("market-status", "children"),
    Input("refresh-interval", "n_intervals")
)
def update_market_status(n_intervals):
    """Check if market is open."""
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    
    # US market hours in CET (roughly 15:30-22:00)
    if weekday < 5 and 15 <= hour < 22:
        return "🟢 Open (US)"
    elif weekday < 5 and (9 <= hour < 15):
        return "🟡 Pre-market"
    else:
        return "🔴 Closed"


# Server reference for gunicorn
server = app.server


if __name__ == "__main__":
    print("=" * 50)
    print("Automatic Trading Factory Dashboard")
    print("=" * 50)
    print(f"Starting on http://{HOST}:{PORT}")
    print(f"Debug mode: {DEBUG}")
    print(f"Refresh interval: {UPDATE_INTERVAL_MS}ms")
    print("=" * 50)
    
    app.run(host=HOST, port=PORT, debug=DEBUG)
