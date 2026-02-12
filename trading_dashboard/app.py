#!/usr/bin/env python3
"""
Automatic Trading Factory Dashboard
Real-time monitoring for trading signals, orders, and portfolio
"""
import sys
from pathlib import Path

# Ensure traderunner local src wins import resolution for axiom_bt.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
from datetime import datetime

from trading_dashboard.config import PORT, HOST, DEBUG, UPDATE_INTERVAL_MS
from trading_dashboard.ui_ids import Nav
from trading_dashboard.auth import add_auth_to_app
from trading_dashboard.layouts import (
    get_live_monitor_content,
    get_charts_content,
    get_portfolio_content,
    get_history_content,
    get_backtests_content,
    get_pre_papertrade_content,
)
from trading_dashboard.layouts.trade_inspector_layout import get_trade_inspector_content
from trading_dashboard.layouts.charts_live import get_charts_live_content
from trading_dashboard.layouts.charts_backtesting import get_charts_backtesting_content
from trading_dashboard.callbacks.chart_callbacks import register_chart_callbacks
from trading_dashboard.callbacks.timeframe_callbacks import register_timeframe_callbacks
from trading_dashboard.callbacks.timezone_callbacks import register_timezone_callbacks
from trading_dashboard.callbacks.history_callbacks import register_history_callbacks
from trading_dashboard.callbacks.active_patterns_callback import register_active_patterns_callback
from trading_dashboard.callbacks.live_data_callback import register_live_data_callback
from trading_dashboard.callbacks.backtests_callbacks import register_backtests_callbacks
from trading_dashboard.callbacks.run_backtest_callback import register_run_backtest_callback
from trading_dashboard.callbacks.pre_papertrade_callbacks import register_pre_papertrade_callbacks
from trading_dashboard.callbacks.period_buttons_callback import register_period_buttons_callback
from trading_dashboard.callbacks.date_selection_callback import register_date_selection_callback
from trading_dashboard.callbacks.symbol_selector_callback import register_symbol_selector_callbacks
from trading_dashboard.callbacks.timestamp_prefix_callback import register_timestamp_prefix_callback
from trading_dashboard.callbacks.freshness_callback import register_freshness_callback
from trading_dashboard.callbacks.charts_live_callbacks import register_charts_live_callbacks
from trading_dashboard.callbacks.charts_backtesting_callbacks import register_charts_backtesting_callbacks
from trading_dashboard.callbacks.trade_inspector_callbacks import register_trade_inspector_callbacks
from trading_dashboard.callbacks.ssot_config_viewer_callback import register_ssot_config_viewer_callback
from trading_dashboard.callbacks.ssot_backtest_config_callback import register_ssot_backtest_config_callback

# Setup logging FIRST
from trading_dashboard.logging_config import setup_logging
setup_logging()

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
            html.Div(id=Nav.HEADER_TIME, style={"color": "var(--text-secondary)"})
        ]
    ),

    # Navigation Tabs
    dbc.Tabs(
        id=Nav.MAIN_TABS,
        active_tab=Nav.TAB_LIVE_MONITOR,
        children=[
            dbc.Tab(label="Live Monitor", tab_id=Nav.TAB_LIVE_MONITOR),
            dbc.Tab(label="Portfolio", tab_id=Nav.TAB_PORTFOLIO),
            dbc.Tab(label="📊 Charts - Live", tab_id=Nav.TAB_CHARTS_LIVE),
            dbc.Tab(label="📈 Charts - Backtesting", tab_id=Nav.TAB_CHARTS_BACKTESTING),
            dbc.Tab(label="History", tab_id=Nav.TAB_HISTORY),
            dbc.Tab(label="Backtests", tab_id=Nav.TAB_BACKTESTS),
            dbc.Tab(label="Pre-PaperTrade Lab", tab_id=Nav.TAB_PRE_PAPERTRADE),
            dbc.Tab(label="🔍 Trade Inspector", tab_id=Nav.TAB_TRADE_INSPECTOR),
        ],
        style={"backgroundColor": "var(--bg-secondary)"}
    ),

    # Tab content
    html.Div(id=Nav.TAB_CONTENT, style={"paddingBottom": "50px"}),

    # Auto-refresh interval (only for Live Monitor tab)
    dcc.Store(id="nav:refresh-policy", data={"bt_job_running": False}),
    dcc.Interval(
        id=Nav.REFRESH_INTERVAL,
        interval=UPDATE_INTERVAL_MS,
        n_intervals=0,
        disabled=False  # Will be controlled by tab switching
    ),

    # Status bar
    html.Div(
        className="status-bar",
        children=[
            html.Span("🟢 Connected", style={"marginRight": "24px"}),
            html.Span(id=Nav.LAST_UPDATE, children="Last update: --"),
            html.Span(" | Market: ", style={"marginLeft": "24px"}),
            html.Span(id=Nav.MARKET_STATUS, children="Checking...")
        ]
    )
])


@app.callback(
    Output(Nav.TAB_CONTENT, "children"),
    Output(Nav.HEADER_TIME, "children"),
    Output(Nav.LAST_UPDATE, "children"),
    Input(Nav.MAIN_TABS, "active_tab"),
    Input(Nav.REFRESH_INTERVAL, "n_intervals")
)
def update_content(active_tab, n_intervals):
    """Update tab content and timestamps."""
    from dash import ctx

    now = datetime.now()
    time_str = now.strftime("%H:%M:%S")
    update_str = f"Last update: {time_str}"

    # Check what triggered this callback
    triggered_id = ctx.triggered_id if ctx.triggered else None

    if active_tab == Nav.TAB_LIVE_MONITOR:
        content = get_live_monitor_content()
    elif active_tab == Nav.TAB_PORTFOLIO:
        content = get_portfolio_content()
    elif active_tab == Nav.TAB_CHARTS_LIVE:
        content = get_charts_live_content()
    elif active_tab == Nav.TAB_CHARTS_BACKTESTING:
        content = get_charts_backtesting_content()
    elif active_tab == "charts":
        # Legacy fallback - redirect to backtesting
        content = get_charts_backtesting_content()
    elif active_tab == Nav.TAB_HISTORY:
        content = get_history_content()
    elif active_tab == Nav.TAB_BACKTESTS:
        content = get_backtests_content()
    elif active_tab == Nav.TAB_PRE_PAPERTRADE:
        content = get_pre_papertrade_content()
    elif active_tab == Nav.TAB_TRADE_INSPECTOR:
        content = get_trade_inspector_content()
    else:
        content = html.Div("Unknown tab")

    return content, time_str, update_str


@app.callback(
    Output(Nav.REFRESH_INTERVAL, "disabled"),
    [
        Input(Nav.MAIN_TABS, "active_tab"),
        Input("nav:refresh-policy", "data")
    ]
)
def control_refresh_interval(active_tab, policy):
    """Enable refresh interval based on Tab and Job Status."""
    is_live = (active_tab == Nav.TAB_LIVE_MONITOR)
    bt_running = bool((policy or {}).get("bt_job_running", False))
    
    # Enabled if Live Monitor OR a Backtest Job is running
    return not (is_live or bt_running)


# Register chart callbacks
register_chart_callbacks(app)
register_timeframe_callbacks(app)
register_timezone_callbacks(app)
register_history_callbacks(app)
register_active_patterns_callback(app)
register_live_data_callback(app)  #  NEW: Live data badges callback
register_backtests_callbacks(app)
register_run_backtest_callback(app)
register_pre_papertrade_callbacks(app)
register_period_buttons_callback(app)
register_date_selection_callback(app)
register_symbol_selector_callbacks(app)
register_timestamp_prefix_callback(app)  # Timestamp prefix display
register_freshness_callback(app)  # Data freshness indicators
register_charts_live_callbacks(app)  # NEW: Live Charts tab
register_charts_backtesting_callbacks(app)  # NEW: Backtesting Charts tab
register_trade_inspector_callbacks(app)
register_ssot_config_viewer_callback(app)  # NEW: SSOT config viewer
register_ssot_backtest_config_callback(app)  # NEW: SSOT backtest config

# Initialize strategy configuration plugins
# MUST be before if __name__ == "__main__" so gunicorn can import it!
from trading_dashboard.strategy_configs.registry import initialize_registry, get_registry
initialize_registry(app)




@app.callback(
    Output(Nav.MARKET_STATUS, "children"),
    Input(Nav.REFRESH_INTERVAL, "n_intervals")
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
