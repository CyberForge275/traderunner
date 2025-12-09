"""Pre-PaperTrade Lab Tab Layout.

Testing environment for strategies - primarily for live intraday trading.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc


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
                                            dbc.Label("Strategy:"),
                                            dcc.Dropdown(
                                                id="pre-papertrade-strategy",
                                                options=[
                                                    {"label": "Inside Bar", "value": "inside_bar"},
                                                    {"label": "Rudometkin MOC", "value": "rudometkin_moc"},
                                                ],
                                                value="inside_bar",
                                                className="mb-3",
                                            ),
                                            
                                            dbc.Label("Symbols (comma-separated):"),
                                            dbc.Input(
                                                id="pre-papertrade-symbols",
                                                placeholder="AAPL,TSLA,NVDA",
                                                value="AAPL,TSLA,NVDA",
                                                className="mb-3",
                                            ),
                                            
                                            dbc.Label("Timeframe:"),
                                            dcc.Dropdown(
                                                id="pre-papertrade-timeframe",
                                                options=[
                                                    {"label": "1 Minute (M1)", "value": "M1"},
                                                    {"label": "5 Minutes (M5)", "value": "M5"},
                                                    {"label": "15 Minutes (M15)", "value": "M15"},
                                                    {"label": "Daily (D)", "value": "D"},
                                                ],
                                                value="M5",
                                                className="mb-3",
                                            ),
                                            
                                            # Strategy-specific config will be injected here
                                            html.Div(id="pre-papertrade-strategy-config"),
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
