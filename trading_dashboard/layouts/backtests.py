"""Backtests Tab Layout - TradeRunner backtest overview and details.

This mirrors the Streamlit backtest dashboard: equity/drawdown charts,
metrics, run log, and orders/fills/trades tables.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd

from ..repositories.backtests import list_backtests


def _create_backtests_table(df):
    if df is None or df.empty:
        return html.Div(
            className="dashboard-card",
            children=[
                html.H5("Backtest Runs"),
                html.P(
                    "No backtests found yet. Trigger a run from TradeRunner to see it here.",
                    className="text-muted",
                    style={"padding": "20px"},
                ),
            ],
        )

    columns = [
        {"name": "Run Name", "id": "run_name"},
        {"name": "Created", "id": "created_at_display"},
        {"name": "Strategy", "id": "strategy"},
        {"name": "Timeframe", "id": "timeframe"},
        {"name": "Symbols", "id": "symbols"},
        {"name": "Status", "id": "status"},
    ]

    return html.Div(
        className="dashboard-card",
        children=[
            html.H5("Backtest Runs", style={"marginBottom": "10px"}),
            dash_table.DataTable(
                id="backtests-table",
                columns=columns,
                data=df.to_dict("records"),
                page_size=5,  # Show 5 rows
                page_action="none",  # Disable pagination
                row_selectable="single",  # Enable row selection
                sort_action="native",  # Enable sorting
                style_table={
                    "overflowY": "auto",  # Enable vertical scrolling
                    "maxHeight": "300px",  # Limit height to ~5 rows
                },
                style_header={
                    "backgroundColor": "var(--bg-secondary)",
                    "color": "var(--text-secondary)",
                    "fontWeight": "bold",
                    "border": "1px solid var(--border-color)",
                    "position": "sticky",
                    "top": 0,
                    "zIndex": 1,
                },
                style_cell={
                    "backgroundColor": "var(--bg-card)",
                    "color": "var(--text-primary)",
                    "border": "1px solid var(--border-color)",
                    "textAlign": "left",
                    "padding": "8px",
                },
            ),
        ],
    )


def _create_metrics_cards(metrics: dict | None):
    metrics = metrics or {}
    return dbc.Row(
        [
            dbc.Col(
                html.Div(
                    className="dashboard-card text-center",
                    children=[
                        html.H6(
                            "Net PnL",
                            style={"color": "var(--text-secondary)", "marginBottom": "5px"},
                        ),
                        html.H3(
                            f"{metrics.get('net_pnl', 0.0):,.3f}",
                            style={"marginBottom": "0"},
                        ),
                    ],
                ),
                width=3,
            ),
            dbc.Col(
                html.Div(
                    className="dashboard-card text-center",
                    children=[
                        html.H6(
                            "Win Rate",
                            style={"color": "var(--text-secondary)", "marginBottom": "5px"},
                        ),
                        html.H3(
                            f"{metrics.get('win_rate', 0.0) * 100:.1f}%"
                            if metrics.get("win_rate") is not None
                            else "--",
                            style={"marginBottom": "0"},
                        ),
                    ],
                ),
                width=3,
            ),
            dbc.Col(
                html.Div(
                    className="dashboard-card text-center",
                    children=[
                        html.H6(
                            "Max Drawdown",
                            style={"color": "var(--text-secondary)", "marginBottom": "5px"},
                        ),
                        html.H3(
                            f"{metrics.get('max_drawdown', 0.0):,.3f}",
                            style={"marginBottom": "0"},
                        ),
                    ],
                ),
                width=3,
            ),
            dbc.Col(
                html.Div(
                    className="dashboard-card text-center",
                    children=[
                        html.H6(
                            "Sharpe Ratio",
                            style={"color": "var(--text-secondary)", "marginBottom": "5px"},
                        ),
                        html.H3(
                            f"{metrics.get('sharpe_ratio', 0.0):.3f}",
                            style={"marginBottom": "0"},
                        ),
                    ],
                ),
                width=3,
            ),
        ],
        style={"marginBottom": "20px"},
    )


def create_backtest_detail(
    run_name: str | None,
    log_df,
    metrics: dict | None,
    summary: dict | None = None,
    equity_df: pd.DataFrame | None = None,
    orders_df: pd.DataFrame | None = None,
    fills_df: pd.DataFrame | None = None,
    trades_df: pd.DataFrame | None = None,
    rk_df: pd.DataFrame | None = None,
):
    if not run_name or log_df is None or log_df.empty:
        return html.Div(
            className="dashboard-card",
            children=[
                html.H5("Backtest Details"),
                html.P(
                    "Select a backtest run from the table to see pipeline steps and metrics.",
                    className="text-muted",
                    style={"padding": "20px"},
                ),
            ],
        )

    summary = summary or {}
    equity_df = equity_df if equity_df is not None else pd.DataFrame()
    orders_df = orders_df if orders_df is not None else pd.DataFrame()
    fills_df = fills_df if fills_df is not None else pd.DataFrame()
    trades_df = trades_df if trades_df is not None else pd.DataFrame()
    rk_df = rk_df if rk_df is not None else pd.DataFrame()

    # Top-level status + strategy info
    status = (summary.get("status") or "unknown").lower()
    strategy_name = summary.get("strategy") or "unknown"
    timeframe = summary.get("timeframe") or "?"
    symbols = summary.get("symbols") or []

    status_badge = html.Span(f"Status: {status}")
    if status.startswith("success"):
        status_badge = html.Span(f"Status: {status}", style={"color": "var(--accent-green)"})
    elif status.startswith("warning"):
        status_badge = html.Span(f"Status: {status}", style={"color": "var(--accent-yellow)"})
    elif status.startswith("error"):
        status_badge = html.Span(f"Status: {status}", style={"color": "var(--accent-red)"})

    header_row = dbc.Row(
        [
            dbc.Col(
                html.Div(
                    className="dashboard-card",
                    children=[
                        html.H5(f"Run: {run_name}"),
                        status_badge,
                    ],
                ),
                width=4,
            ),
            dbc.Col(
                html.Div(
                    className="dashboard-card",
                    children=[
                        html.H6("Strategy / Timeframe", style={"marginBottom": "6px"}),
                        html.Div(f"Strategy: {strategy_name}"),
                        html.Div(f"Timeframe: {timeframe}"),
                        html.Div(f"Symbols: {', '.join(symbols) if symbols else 'n/a'}"),
                    ],
                ),
                width=8,
            ),
        ],
        style={"marginBottom": "20px"},
    )

    metrics_cards = _create_metrics_cards(metrics)

    # Equity / Drawdown charts (from equity_curve.csv if available)
    charts_row_children = []
    if not equity_df.empty and "ts" in equity_df.columns:
        df_chart = equity_df.copy()
        df_chart["ts"] = pd.to_datetime(df_chart["ts"], errors="coerce")
        df_chart = df_chart.dropna(subset=["ts"]).sort_values("ts")

        equity_fig = px.line(df_chart, x="ts", y="equity", title="Equity curve")
        equity_fig.update_layout(margin=dict(l=40, r=20, t=40, b=40))

        dd_fig = None
        if "drawdown_pct" in df_chart.columns:
            dd_fig = px.line(df_chart, x="ts", y="drawdown_pct", title="Drawdown (pct)")
            dd_fig.update_layout(margin=dict(l=40, r=20, t=40, b=40))

        charts_row_children = [
            dbc.Col(
                html.Div(
                    className="dashboard-card",
                    children=[
                        html.H5("Equity curve"),
                        dcc.Graph(figure=equity_fig, config={"displayModeBar": False}),
                    ],
                ),
                width=6,
            ),
            dbc.Col(
                html.Div(
                    className="dashboard-card",
                    children=[
                        html.H5("Drawdown (pct)"),
                        dcc.Graph(
                            figure=dd_fig,
                            config={"displayModeBar": False},
                        )
                        if dd_fig is not None
                        else html.Div("No drawdown data found."),
                    ],
                ),
                width=6,
            ),
        ]

    charts_row = (
        dbc.Row(charts_row_children, style={"marginBottom": "20px"})
        if charts_row_children
        else html.Div()
    )

    # Full metrics table (all metrics.json keys)
    metrics_table = html.Div()
    if metrics:
        metrics_items = sorted(metrics.items())
        metrics_df = pd.DataFrame(metrics_items, columns=["Metric", "Value"])
        metrics_table = html.Div(
            className="dashboard-card",
            children=[
                html.H5("Metrics"),
                dash_table.DataTable(
                    id="backtests-metrics-table",
                    columns=[
                        {"name": "Metric", "id": "Metric"},
                        {"name": "Value", "id": "Value"},
                    ],
                    data=metrics_df.to_dict("records"),
                    page_size=20,
                    style_table={"overflowX": "auto"},
                    style_header={
                        "backgroundColor": "var(--bg-secondary)",
                        "color": "var(--text-secondary)",
                        "fontWeight": "bold",
                        "border": "1px solid var(--border-color)",
                    },
                    style_cell={
                        "backgroundColor": "var(--bg-card)",
                        "color": "var(--text-primary)",
                        "border": "1px solid var(--border-color)",
                        "textAlign": "left",
                        "padding": "8px",
                    },
                ),
            ],
        )

    # Run log & performance (per-step durations + raw log)
    log_table = dash_table.DataTable(
        id="backtests-log-table",
        columns=[
            {"name": "Step", "id": "title"},
            {"name": "Kind", "id": "kind"},
            {"name": "Status", "id": "status"},
            {"name": "Duration (s)", "id": "duration"},
            {"name": "Details", "id": "details"},
        ],
        data=log_df.to_dict("records"),
        page_size=20,
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "var(--bg-secondary)",
            "color": "var(--text-secondary)",
            "fontWeight": "bold",
            "border": "1px solid var(--border-color)",
        },
        style_cell={
            "backgroundColor": "var(--bg-card)",
            "color": "var(--text-primary)",
            "border": "1px solid var(--border-color)",
            "textAlign": "left",
            "padding": "8px",
            "whiteSpace": "normal",
            "height": "auto",
        },
    )

    step_summary = html.Div()
    if "duration" in log_df.columns and "title" in log_df.columns:
        try:
            summary_df = (
                log_df.groupby("title")["duration"]
                .sum()
                .reset_index()
                .sort_values("duration", ascending=False)
            )
            step_summary = dash_table.DataTable(
                id="backtests-log-summary",
                columns=[
                    {"name": "Step", "id": "title"},
                    {"name": "Total Duration (s)", "id": "duration"},
                ],
                data=summary_df.to_dict("records"),
                page_size=20,
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": "var(--bg-secondary)",
                    "color": "var(--text-secondary)",
                    "fontWeight": "bold",
                    "border": "1px solid var(--border-color)",
                },
                style_cell={
                    "backgroundColor": "var(--bg-card)",
                    "color": "var(--text-primary)",
                    "border": "1px solid var(--border-color)",
                    "textAlign": "left",
                    "padding": "8px",
                },
            )
        except Exception:
            step_summary = html.Div()

    log_block = html.Div(
        className="dashboard-card",
        children=[
            html.H5("Run log & performance"),
            html.H6("Per-step durations (s)", style={"marginTop": "10px"}),
            step_summary,
            html.H6("Raw log entries", style={"marginTop": "20px"}),
            log_table,
        ],
    )

    # Orders / Filled Orders / Trades tabs
    tabs_children = []

    def _format_numeric(df: pd.DataFrame, cols: list[str], digits: int = 2) -> pd.DataFrame:
        if df.empty:
            return df
        out = df.copy()
        for col in cols:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce").round(digits)
        return out

    # Orders
    orders_content = html.Div("No orders available.")
    if not orders_df.empty:
        display_orders = _format_numeric(orders_df, ["price", "stop_loss", "take_profit"])
        orders_content = dash_table.DataTable(
            id="backtests-orders-table",
            columns=[{"name": c, "id": c} for c in display_orders.columns],
            data=display_orders.to_dict("records"),
            page_size=20,
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "var(--bg-secondary)",
                "color": "var(--text-secondary)",
                "fontWeight": "bold",
                "border": "1px solid var(--border-color)",
            },
            style_cell={
                "backgroundColor": "var(--bg-card)",
                "color": "var(--text-primary)",
                "border": "1px solid var(--border-color)",
                "textAlign": "left",
                "padding": "8px",
            },
        )

    # Filled orders
    fills_content = html.Div("No filled orders available.")
    if not fills_df.empty:
        display_fills = fills_df.copy()
        if {"entry_price", "qty"}.issubset(display_fills.columns):
            display_fills["entry_notional"] = (
                pd.to_numeric(display_fills["entry_price"], errors="coerce")
                * pd.to_numeric(display_fills["qty"], errors="coerce")
            ).round(2)
        fee_cols = [
            "fees_entry",
            "fees_exit",
            "fees_total",
            "slippage_entry",
            "slippage_exit",
            "slippage_total",
        ]
        display_fills = _format_numeric(display_fills, fee_cols, digits=2)
        fills_content = dash_table.DataTable(
            id="backtests-fills-table",
            columns=[{"name": c, "id": c} for c in display_fills.columns],
            data=display_fills.to_dict("records"),
            page_size=20,
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "var(--bg-secondary)",
                "color": "var(--text-secondary)",
                "fontWeight": "bold",
                "border": "1px solid var(--border-color)",
            },
            style_cell={
                "backgroundColor": "var(--bg-card)",
                "color": "var(--text-primary)",
                "border": "1px solid var(--border-color)",
                "textAlign": "left",
                "padding": "8px",
            },
        )

    # Trades
    trades_content = html.Div("No trades available.")
    if not trades_df.empty:
        fee_cols = [
            "fees_entry",
            "fees_exit",
            "fees_total",
            "slippage_entry",
            "slippage_exit",
            "slippage_total",
        ]
        display_trades = _format_numeric(trades_df, fee_cols, digits=2)
        trades_content = dash_table.DataTable(
            id="backtests-trades-table",
            columns=[{"name": c, "id": c} for c in display_trades.columns],
            data=display_trades.to_dict("records"),
            page_size=20,
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "var(--bg-secondary)",
                "color": "var(--text-secondary)",
                "fontWeight": "bold",
                "border": "1px solid var(--border-color)",
            },
            style_cell={
                "backgroundColor": "var(--bg-card)",
                "color": "var(--text-primary)",
                "border": "1px solid var(--border-color)",
                "textAlign": "left",
                "padding": "8px",
            },
        )

    tabs_children = [
        dcc.Tab(label="Orders", children=orders_content),
        dcc.Tab(label="Filled Orders", children=fills_content),
        dcc.Tab(label="Trades", children=trades_content),
    ]

    # Rudometkin daily candidates (optional)
    rk_block = html.Div()
    if not rk_df.empty:
        longs = rk_df[rk_df.get("long_entry").notna()] if "long_entry" in rk_df.columns else rk_df.iloc[0:0]
        shorts = rk_df[rk_df.get("short_entry").notna()] if "short_entry" in rk_df.columns else rk_df.iloc[0:0]
        rk_metrics_row = dbc.Row(
            [
                dbc.Col(html.Div([html.H6("Total Candidates"), html.Div(str(len(rk_df)))])),
                dbc.Col(html.Div([html.H6("LONG Candidates"), html.Div(str(len(longs)))])),
                dbc.Col(html.Div([html.H6("SHORT Candidates"), html.Div(str(len(shorts)))])),
            ],
            style={"marginBottom": "10px"},
        )

        display_daily = rk_df.copy()
        for col in ["long_entry", "short_entry", "sl_long", "sl_short", "tp_long", "tp_short"]:
            if col in display_daily.columns:
                display_daily[col] = pd.to_numeric(display_daily[col], errors="coerce").round(2)
        if "score" in display_daily.columns:
            display_daily["score"] = pd.to_numeric(display_daily["score"], errors="coerce").round(4)

        rk_table = dash_table.DataTable(
            id="backtests-rk-table",
            columns=[{"name": c, "id": c} for c in display_daily.columns],
            data=display_daily.to_dict("records"),
            page_size=20,
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "var(--bg-secondary)",
                "color": "var(--text-secondary)",
                "fontWeight": "bold",
                "border": "1px solid var(--border-color)",
            },
            style_cell={
                "backgroundColor": "var(--bg-card)",
                "color": "var(--text-primary)",
                "border": "1px solid var(--border-color)",
                "textAlign": "left",
                "padding": "8px",
            },
        )

        rk_block = html.Div(
            className="dashboard-card",
            children=[
                html.H5("Rudometkin Daily Candidates"),
                rk_metrics_row,
                rk_table,
            ],
        )

    return html.Div(
        className="dashboard-card",
        children=[
            header_row,
            metrics_cards,
            charts_row,
            metrics_table,
            log_block,
            html.Div(
                className="dashboard-card",
                children=[
                    html.H5("Orders / Fills / Trades"),
                    dcc.Tabs(children=tabs_children),
                ],
                style={"marginTop": "20px"},
            ),
            rk_block,
        ],
    )


def create_backtests_layout():
    """Create the Backtests tab layout.

    Left pane: strategy selection, run selection, and basic run metadata.
    Right pane: runs table and detailed backtest output (charts, logs, orders).
    """

    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)

    df = list_backtests(start_date=week_ago, end_date=today)
    table = _create_backtests_table(df)

    # Strategy filter options based on available runs
    strategy_options = [
        {"label": "All Strategies", "value": "all"},
    ]
    run_options = []
    if df is not None and not df.empty:
        strategies = sorted(df["strategy"].dropna().unique().tolist())
        strategy_options.extend({"label": s, "value": s} for s in strategies)

        run_options = [
            {"label": row["run_name"], "value": row["run_name"]}
            for _, row in df.iterrows()
        ]

    # Left pane: controls for strategy, run selection, and basic run info
    strategy_card = html.Div(
        className="dashboard-card",
        children=[
            html.H6("Filter Existing Runs", style={"marginBottom": "10px"}),
            html.Label("Strategy", style={"fontSize": "0.9em", "color": "var(--text-secondary)"}),
            dcc.Dropdown(
                id="backtests-strategy-filter",
                options=strategy_options,
                value="all",
                clearable=False,
                style={"color": "#000"},
            ),
        ],
    )

    # NEW: Strategy configuration for running new backtests
    new_backtest_card = html.Div(
        className="dashboard-card",
        children=[
            html.H6("📊 New Backtest Configuration", style={"marginBottom": "15px"}),
            
            # Strategy selector
            html.Label("Strategy", style={"fontWeight": "bold", "marginTop": "8px"}),
            dcc.Dropdown(
                id="backtests-new-strategy",
                options=[
                    {"label": "Inside Bar", "value": "insidebar_intraday"},
                    {"label": "Inside Bar V2", "value": "insidebar_intraday_v2"},
                    {"label": "Rudometkin", "value": "rudometkin_moc_mode"},
                ],
                value="insidebar_intraday",
                clearable=False,
                style={"color": "#000", "marginBottom": "8px"},
            ),
            
            # Version selector (conditional - only for versioned strategies)
            html.Div(
            ),
            
            # Run name input with timestamp prefix
            html.Label("Backtest Run Name", style={"fontWeight": "bold", "marginTop": "8px"}),
            html.Div([
                html.Span(
                    id="run-name-timestamp-prefix",
                    children="251207_225402_",  # Will be updated by callback
                    style={
                        "color": "#888",  # Light grey
                        "fontSize": "0.95em",
                        "lineHeight": "38px",  # Match input height
                        "paddingRight": "4px",
                        "fontFamily": "monospace",
                    }
                ),
                dcc.Input(
                    id="backtests-new-run-name",
                    type="text",
                    placeholder="YourNameHere",
                    style={
                        "flex": "1",
                        "marginBottom": "8px",
                    },
                ),
            ], style={"display": "flex", "alignItems": "center"}),
            
            # Symbols input with cached selector
            html.Label("Symbols (comma-separated)", style={"fontWeight": "bold", "marginTop": "8px"}),
            html.Div([
                dcc.Dropdown(
                    id="cached-symbols-selector",
                    options=[],  # Will be populated by callback based on timeframe
                    multi=True,
                    placeholder="Select from cached symbols...",
                    style={"marginBottom": "4px", "color": "#000"},
                ),
                dcc.Input(
                    id="backtests-new-symbols",
                    type="text",
                    placeholder="Or type: TSLA,AAPL,PLTR,HOOD",
                    value="",  # Empty by default
                    style={"width": "100%", "marginBottom": "8px"},
                ),
            ]),
            
            # Timeframe selector
            html.Label("Timeframe", style={"fontWeight": "bold", "marginTop": "8px"}),
            dcc.Dropdown(
                id="backtests-new-timeframe",
                options=[
                    {"label": "5 Min (M5)", "value": "M5"},
                    {"label": "15 Min (M15)", "value": "M15"},
                    {"label": "1 Hour (H1)", "value": "H1"},
                    {"label": "1 Day (D1)", "value": "D1"},
                ],
                value="M5",
                clearable=False,
                style={"color": "#000", "marginBottom": "8px"},
            ),
            
            
            # Date selection method (Streamlit-style)
            html.Label("Date Selection", style={"fontWeight": "bold", "marginTop": "8px"}),
            dcc.RadioItems(
                id="date-selection-mode",
                options=[
                    {"label": "Days back from anchor", "value": "days_back"},
                    {"label": "Explicit date range", "value": "explicit"},
                ],
                value="days_back",
                style={"marginBottom": "8px"},
            ),
            
            # Anchor date (for days back mode)
            html.Div(
                id="anchor-date-container",
                children=[
                    html.Label("Anchor Date", style={"fontSize": "0.9em", "marginTop": "5px"}),
                    dcc.DatePickerSingle(
                        id="anchor-date",
                        date=datetime.utcnow().date(),
                        display_format="YYYY-MM-DD",
                        style={"width": "100%", "marginBottom": "8px"},
                    ),
                ],
            ),
            
            # Days back (for days back mode)
            html.Div(
                id="days-back-container",
                children=[
                    html.Label("Days back", style={"fontSize": "0.9em", "marginTop": "5px"}),
                    dcc.Input(
                        id="days-back",
                        type="number",
                        value=4,  # Changed from 30 to 4
                        min=1,
                        max=365,
                        step=1,
                        style={"width": "100%", "marginBottom": "8px"},
                    ),
                ],
            ),
            
            # Explicit date range (for explicit mode)
            html.Div(
                id="explicit-range-container",
                children=[
                    html.Label("Start Date", style={"fontSize": "0.9em", "marginTop": "5px"}),
                    dcc.DatePickerSingle(
                        id="explicit-start-date",
                        date=(datetime.utcnow() - timedelta(days=30)).date(),
                        display_format="YYYY-MM-DD",
                        style={"width": "100%", "marginBottom": "8px"},
                    ),
                    html.Label("End Date", style={"fontSize": "0.9em", "marginTop": "5px"}),
                    dcc.DatePickerSingle(
                        id="explicit-end-date",
                        date=datetime.utcnow().date(),
                        display_format="YYYY-MM-DD",
                        style={"width": "100%", "marginBottom": "8px"},
                    ),
                ],
                style={"display": "none"},  # Hidden by default
            ),
            
            # Data window display
            html.Div(
                id="data-window-display",
                style={
                    "fontSize": "0.85em",
                    "color": "var(--text-secondary)",
                    "padding": "8px",
                    "backgroundColor": "rgba(255,255,255,0.05)",
                    "borderRadius": "4px",
                    "marginBottom": "8px"},
            ),
            
            
            # Run button
            dbc.Button(
                "▶ Run Backtest",
                id="backtests-run-button",
                color="success",
                className="w-100",
                style={"marginTop": "10px", "fontWeight": "bold"},
            ),
            
            # Progress indicator
            html.Div(id="backtests-run-progress", style={"marginTop": "12px"}),
        ],
        style={"marginTop": "20px"},
    )

    run_select_card = html.Div(
        className="dashboard-card",
        children=[
            html.H6("Previous Runs", style={"marginBottom": "10px"}),
            dcc.Dropdown(
                id="backtests-run-select",
                options=run_options,
                value=run_options[0]["value"] if run_options else None,
                placeholder="Select a run…",
                clearable=True,
                style={"color": "#000"},
            ),
            html.Hr(),
            html.H6("Backtest Run Name", style={"marginBottom": "10px"}),
            dcc.Input(
                id="backtests-run-name-input",
                type="text",
                placeholder="Name for new backtest run",
                style={"width": "100%"},
            ),
            html.P(
                "Parameters (reserved for future backtest launch)",
                className="text-muted",
                style={"marginTop": "10px", "marginBottom": "4px"},
            ),
            dcc.Textarea(
                id="backtests-run-params",
                placeholder="e.g. initial_cash=10000, risk_pct=1.0",
                style={"width": "100%", "height": "70px", "color": "#000"},
            ),
        ],
        style={"marginTop": "20px"},
    )

    left_pane = html.Div([strategy_card, new_backtest_card, run_select_card])

    right_pane = html.Div(
        [
            html.Div(table, style={"marginBottom": "20px"}),
            html.Div(id="backtests-detail"),
        ]
    )
    
    # Hidden interval for auto-refresh when job completes
    refresh_interval = dcc.Interval(
        id="backtests-refresh-interval",
        interval=5000,  # 5 seconds
        n_intervals=0,
        disabled=True  # Enabled via callback when job is running
    )

    return html.Div([
        refresh_interval,
        dbc.Row(
            [
                dbc.Col(left_pane, width=3),
                dbc.Col(right_pane, width=9),
            ],
            style={"padding": "20px"},
        )
    ])



def get_backtests_content():
    """Callback-friendly entrypoint for Backtests tab content."""

    return create_backtests_layout()
