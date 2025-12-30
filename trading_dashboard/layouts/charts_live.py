"""
Charts - Live Tab Layout
=========================

Live market data from WebSocket/SQLite ONLY.

CRITICAL ARCHITECTURE RULE:
- This module MUST NOT import IntradayStore or read_parquet
- Data source: SQLite (LiveCandlesRepository)
- Architecture tests enforce this constraint
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime
import os

def create_charts_live_layout():
    """Create the Live Charts tab layout."""

    # Get symbols from ENV (SSOT)
    symbols_env = os.getenv('EODHD_SYMBOLS', '')
    symbols = [s.strip().upper() for s in symbols_env.split(',') if s.strip()]

    if not symbols:
        # Fallback for local development
        symbols = ['AAL', 'AAPL', 'TSLA']

    return html.Div([
        # Header
        dbc.Row([
            dbc.Col([
                html.H4("📊 Live Charts", style={"color": "#00d26a"}),
                html.P("Real-time market data (WebSocket/SQLite)",
                       className="text-muted", style={"fontSize": "0.9rem"}),
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button("🔄 Refresh", id="live-refresh-btn", color="primary", size="sm"),
                    dbc.Button("🕐 NY Time", id="live-tz-ny-btn", color="primary", size="sm"),
                    dbc.Button("🕐 Berlin Time", id="live-tz-berlin-btn", color="secondary", size="sm", outline=True),
                ]),
            ], width=4, className="text-end"),
        ], className="mb-3"),

        dbc.Row([
            # Sidebar
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        # Data Source Label (prominent)
                        html.Div([
                            html.Span("🔴", style={"fontSize": "1.2rem", "marginRight": "8px"}),
                            html.Strong("LIVE", style={"fontSize": "1.1rem", "color": "#00d26a"}),
                            html.Br(),
                            html.Small("source: LIVE_SQLITE",
                                     className="text-muted", style={"fontSize": "0.7rem"}),
                        ], style={
                            "padding": "10px",
                            "backgroundColor": "#1a1a1a",
                            "borderRadius": "5px",
                            "marginBottom": "15px",
                            "textAlign": "center"
                        }),

                        html.Hr(),

                        # Symbol Selector
                        html.H6("Symbol"),
                        dcc.Dropdown(
                            id="live-symbol-selector",
                            options=[{"label": sym, "value": sym} for sym in symbols],
                            value=symbols[0] if symbols else None,
                            clearable=False,
                            style={
                                "backgroundColor": "#2b2b2b",
                                "color": "#ffffff",
                            },
                            className="custom-dropdown mb-3"
                        ),

                        # Timeframe Buttons (M1/M5/M15 only)
                        html.H6("Timeframe", className="mt-3"),
                        dbc.ButtonGroup([
                            dbc.Button("M1", id="live-tf-m1", size="sm", outline=True, color="secondary"),
                            dbc.Button("M5", id="live-tf-m5", size="sm", active=True, color="primary"),
                            dbc.Button("M15", id="live-tf-m15", size="sm", outline=True, color="secondary"),
                        ], vertical=True, style={"width": "100%"}, className="mb-3"),

                        html.Hr(),

                        # Freshness Indicator
                        html.H6("📊 Data Freshness"),
                        html.Div(id="live-freshness-indicator", children=[
                            html.Div([
                                html.Span("Last Update: ", style={"fontWeight": "bold", "fontSize": "0.75rem"}),
                                html.Br(),
                                html.Span("Checking...", id="live-freshness-text",
                                        style={"fontSize": "0.75rem"}),
                                html.Span(" ", id="live-freshness-badge",
                                        style={"marginLeft": "5px", "fontSize": "1.2rem"})
                            ]),
                        ]),
                        html.P(
                            "🟢 Fresh (<5m)  🟡 Stale (>5m)  🔴 Missing",
                            className="text-muted",
                            style={"fontSize": "0.7rem", "marginTop": "10px"}
                        ),

                        html.Hr(),

                        # Info
                        html.Div([
                            html.H6("ℹ️ Live Data Info", style={"fontSize": "0.85rem"}),
                            html.P("• All sessions included",
                                  className="text-muted", style={"fontSize": "0.75rem", "margin": "0"}),
                            html.P("• 30-day retention",
                                  className="text-muted", style={"fontSize": "0.75rem", "margin": "0"}),
                            html.P("• Up to 50 symbols",
                                  className="text-muted", style={"fontSize": "0.75rem", "margin": "0"}),
                            html.P("• Real-time WebSocket feed",
                                  className="text-muted", style={"fontSize": "0.75rem", "margin": "0"}),
                        ], style={"marginTop": "15px"}),
                    ])
                ])
            ], width=2),

            # Chart Area
            dbc.Col([
                dcc.Loading(
                    id="live-loading-chart",
                    type="default",
                    children=[
                        dcc.Graph(
                            id="live-candlestick-chart",
                            style={"height": "700px"}
                        )
                    ]
                )
            ], width=10),
        ]),
    ], style={"padding": "20px"})


def get_charts_live_content():
    """Get Live charts content for callbacks."""
    return create_charts_live_layout()
