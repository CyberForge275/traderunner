"""Pre-PaperTrade Lab Tab Layout.

Testing environment for strategies - primarily for live intraday trading.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc


def _get_strategy_options():
    """Get combined strategy+version options."""
    try:
        from trading_dashboard.utils.version_loader import get_all_strategy_versions_combined
        options = get_all_strategy_versions_combined()
        if options:
            return options
    except Exception as e:
        print(f"Error loading strategy versions: {e}")

    # Fallback to basic strategy list (no versions)
    return [
        {
            "label": "Inside Bar (no versions available)",
            "value": "insidebar_intraday"
        },
        {
            "label": "InsideBarv2 (no versions available)",
            "value": "insidebar_intraday_v2"
        },
        {
            "label": "Rudometkin MOC (no versions available)",
            "value": "rudometkin_moc_mode"
        },
    ]


def create_pre_papertrade_layout():
    """
    Create the Pre-PaperTrade Lab tab layout.

    Left pane: Mode selection, strategy configuration, run controls
    Right pane: Signals output, statistics, and history
    """

    return dbc.Container(
        [
            dbc.Row(
                [
                    # Left Column: Configuration and Controls
                    dbc.Col(
                        [
                            html.H4("Pre-PaperTrade Lab", className="mb-3"),
                            html.P(
                                "Run strategies live during market hours or replay past sessions with Time Machine.",
                                className="text-muted mb-4",
                            ),

                            # Mode Selection
                            dbc.Card(
                                [
                                    dbc.CardHeader("Mode Selection"),
                                    dbc.CardBody(
                                        [
                                            dbc.RadioItems(
                                                id="pre-papertrade-mode",
                                                options=[
                                                    {"label": "🔴 Live (Real-time)", "value": "live"},
                                                    {"label": "⏰ Time Machine (Replay Past Day)", "value": "replay"},
                                                ],
                                                value="live",
                                                className="mb-3",
                                            ),
                                            html.Div(
                                                id="mode-description",
                                                children=[
                                                    html.Small(
                                                        "Live mode: Run strategy in real-time during market hours. "
                                                        "Signals generated from live market data.",
                                                        className="text-muted",
                                                    ),
                                                ],
                                            ),
                                        ]
                                    ),
                                ],
                                className="mb-3",
                            ),

                            # Time Machine Configuration (only visible in replay mode)
                            html.Div(
                                id="time-machine-container",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader("⏰ Time Machine - Replay Past Session"),
                                            dbc.CardBody(
                                                [
                                                    dbc.Label("Select Date to Replay:"),
                                                    dcc.DatePickerSingle(
                                                        id="replay-single-date",
                                                        date=(datetime.now() - timedelta(days=1)).date(),
                                                        display_format="YYYY-MM-DD",
                                                        className="mb-2",
                                                    ),
                                                    html.Small(
                                                        "Replay the entire trading session from this date using historical data.",
                                                        className="text-muted",
                                                    ),
                                                ]
                                            ),
                                        ],
                                        className="mb-3",
                                    ),
                                ],
                                style={"display": "none"},  # Hidden by default (live mode)
                            ),

                            # Strategy Configuration
                            dbc.Card(
                                [
                                    dbc.CardHeader("Strategy Configuration"),
                                    dbc.CardBody(
                                        [
                                            # Strategy Selection
                                            dbc.Label("Select Strategy Version:", className="fw-bold"),
                                            dcc.Dropdown(
                                                id="pre-papertrade-strategy",
                                                options=_get_strategy_options(),
                                                value="insidebar_intraday",  # Default to V1
                                                clearable=False,
                                                className="mb-3",
                                            ),
                                            html.Small(
                                                id="strategy-description",
                                                className="text-muted mb-3 d-block",
                                                children="Inside Bar Intraday - Pattern breakout strategy"
                                            ),

                                            html.Hr(),

                                            # Symbols
                                            dbc.Label("Symbols (comma-separated):"),
                                            dbc.Input(
                                                id="pre-papertrade-symbols",
                                                type="text",
                                                placeholder="AAPL,TSLA,NVDA",
                                                value="",
                                                className="mb-3",
                                            ),

                                            # Timeframe
                                            dbc.Label("Timeframe:"),
                                            dcc.Dropdown(
                                                id="pre-papertrade-timeframe",
                                                options=[
                                                    {"label": "M1 (1 minute)", "value": "M1"},
                                                    {"label": "M5 (5 minutes)", "value": "M5"},
                                                    {"label": "M15 (15 minutes)", "value": "M15"},
                                                    {"label": "M30 (30 minutes)", "value": "M30"},
                                                    {"label": "H1 (1 hour)", "value": "H1"},
                                                    {"label": "D (Daily)", "value": "D"},
                                                ],
                                                value="M5",
                                                clearable=False,
                                                className="mb-3",
                                            ),

                                            html.Hr(),

                                            # NEW: Session Filter Input
                                            dbc.Label("Session Hours (optional):", className="fw-bold"),
                                            dbc.Input(
                                                id="session-filter-input",
                                                type="text",
                                                placeholder="15:00-16:00,16:00-17:00",
                                                value="",
                                                className="mb-2",
                                            ),
                                            dbc.FormText(
                                                "Enter time windows to filter signals (24-hour format). "
                                                "Leave empty for no filtering (all time periods). "
                                                "Example: 15:00-17:00",
                                                color="secondary",
                                                className="mb-3"
                                            ),

                                            html.Hr(),

                                            # Strategy Parameters (for now, static - Phase 3 will make dynamic)
                                            html.Div(
                                                id="strategy-parameters-container",
                                                children=[
                                                    dbc.Label("Strategy Parameters:", className="fw-bold mb-2"),
                                                    html.Small(
                                                        "Basic parameters shown. Advanced parameters passed automatically based on strategy version.",
                                                        className="text-muted d-block mb-3"
                                                    ),
                                                ]
                                            ),
                                        ]
                                    ),
                                ],
                                className="mb-3",
                            ),

                            # NEW: Past Runs Selector
                            dbc.Card(
                                [
                                    dbc.CardHeader("📂 Load Previous Test"),
                                    dbc.CardBody(
                                        [
                                            dbc.Label("Select Past Run:"),
                                            dcc.Dropdown(
                                                id="past-runs-dropdown",
                                                options=[],  # Will be populated by callback
                                                placeholder="Select a previous test...",
                                                clearable=True,
                                                className="mb-2",
                                            ),
                                            html.Small(
                                                "Load results from a previous Pre-PaperTrade test",
                                                className="text-muted"
                                            ),
                                        ]
                                    ),
                                ],
                                className="mb-3",
                            ),

                            # Run Controls
                            dbc.Card(
                                [
                                    dbc.CardBody(
                                        [
                                            dbc.Button(
                                                "▶ Start",
                                                id="run-pre-papertrade-btn",
                                                color="primary",
                                                size="lg",
                                                className="w-100 mb-2",
                                            ),
                                            dbc.Button(
                                                "🗑️ Clear Signals",
                                                id="clear-signals-btn",
                                                color="warning",
                                                outline=True,
                                                size="sm",
                                                className="w-100",
                                            ),
                                        ]
                                    ),
                                ],
                            ),
                        ],
                        md=4,
                    ),

                    # Right Column: Results and Output
                    dbc.Col(
                        [
                            # Status/Progress
                            dbc.Alert(
                                id="pre-papertrade-status",
                                children="Ready - Select mode and click Start",
                                color="info",
                                className="mb-3",
                            ),

                            # Statistics Cards
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.H2(id="signals-total", children="0", className="mb-0"),
                                                        html.P("Total Signals", className="text-muted mb-0"),
                                                    ]
                                                ),
                                            ],
                                            className="text-center",
                                        ),
                                        md=4,
                                    ),
                                    dbc.Col(
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.H2(id="signals-buy", children="0", className="mb-0 text-success"),
                                                        html.P("BUY Signals", className="text-muted mb-0"),
                                                    ]
                                                ),
                                            ],
                                            className="text-center",
                                        ),
                                        md=4,
                                    ),
                                    dbc.Col(
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.H2(id="signals-sell", children="0", className="mb-0 text-danger"),
                                                        html.P("SELL Signals", className="text-muted mb-0"),
                                                    ]
                                                ),
                                            ],
                                            className="text-center",
                                        ),
                                        md=4,
                                    ),
                                ],
                                className="mb-3",
                            ),

                            # Signals Table
                            dbc.Card(
                                [
                                    dbc.CardHeader("Generated Signals"),
                                    dbc.CardBody(
                                        [
                                            dash_table.DataTable(
                                                id="signals-table",
                                                columns=[
                                                    {"name": "Symbol", "id": "symbol"},
                                                    {"name": "Side", "id": "side"},
                                                    {"name": "Entry", "id": "entry_price"},
                                                    {"name": "Stop Loss", "id": "stop_loss"},
                                                    {"name": "Take Profit", "id": "take_profit"},
                                                    {"name": "Detected At", "id": "detected_at"},
                                                    {"name": "Status", "id": "status"},
                                                ],
                                                data=[],
                                                page_size=10,
                                                style_table={"overflowX": "auto"},
                                                style_cell={
                                                    "textAlign": "left",
                                                    "padding": "8px",
                                                },
                                                style_data_conditional=[
                                                    {
                                                        "if": {"filter_query": "{side} = BUY"},
                                                        "backgroundColor": "#d4edda",
                                                        "color": "#155724",
                                                    },
                                                    {
                                                        "if": {"filter_query": "{side} = SELL"},
                                                        "backgroundColor": "#f8d7da",
                                                        "color": "#721c24",
                                                    },
                                                ],
                                            ),
                                        ]
                                    ),
                                ],
                            ),

                            # NEW: Run History Panel (InsideBar Pre-Paper only)
                            html.Div(
                                id="run-history-container",
                                children=[],  # Will be populated by callback
                                className="mt-3"
                            ),
                        ],
                        md=8,
                    ),
                ],
            ),

            # Hidden stores
            dcc.Store(id="pre-papertrade-job-status", data={"status": "idle"}),
            dcc.Interval(id="pre-papertrade-interval", interval=2000, disabled=True),
        ],
        fluid=True,
        className="p-4",
    )


def get_pre_papertrade_content():
    """Callback-friendly entrypoint for Pre-PaperTrade tab content."""
    return create_pre_papertrade_layout()
