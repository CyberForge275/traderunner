from __future__ import annotations

from dash import html, dcc
import dash_bootstrap_components as dbc


def get_trade_inspector_content():
    return html.Div(
        className="dashboard-section",
        children=[
            html.H4("🔍 Trade Inspector"),
            dbc.Row([
                dbc.Col(
                    [
                        html.Label("Run"),
                        dcc.Dropdown(id="ti-run-dropdown", placeholder="Select run"),
                        html.Br(),
                        html.Label("Trade"),
                        dcc.Dropdown(id="ti-trade-dropdown", placeholder="Select trade"),
                        html.Br(),
                        html.Div(id="ti-trades-table"),
                        dcc.Store(id="ti-resize-request", data={"req": 0}),
                        dcc.Store(id="ti-resize-ack", data={"req_seen": 0}),
                    ],
                    width=4,
                ),
                dbc.Col(
                    [
                        html.Div(id="ti-trade-summary"),
                        html.Div(
                            dcc.Graph(
                                id="ti-trade-chart",
                                className="ti-chart-graph",
                                config={
                                    "displayModeBar": True,  # Show modebar for zoom/pan controls
                                    "modeBarButtonsToRemove": [
                                        "select2d",
                                        "lasso2d",
                                        "autoScale2d",
                                    ],
                                    "displaylogo": False,
                                },
                                style={"height": "600px", "width": "100%"},  # Responsive width
                                responsive=False,  # Keep Dash responsive mode off to prevent loops
                            ),
                            className="ti-chart-shell",
                            style={"width": "100%"},  # Allow container to be responsive
                        ),
                        html.Div(id="ti-evidence-status"),
                    ],
                    width=8,
                ),
            ])
        ],
    )
