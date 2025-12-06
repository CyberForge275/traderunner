"""
Charts Tab Layout - Interactive candlestick with pattern overlay
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime

from ..components.candlestick import get_chart_config
from ..repositories import get_watchlist_symbols


def create_charts_layout():
    """Create the Charts tab layout."""
    symbols = get_watchlist_symbols()
    
    return html.Div([
        # Controls row at top
        dbc.Row([
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button("🔄 Refresh Chart", id="chart-refresh-btn", color="primary", size="sm"),
                    dbc.Button("🕐 NY Time", id="tz-ny-btn", color="secondary", size="sm", outline=True),
                    dbc.Button("🕐 Berlin Time", id="tz-berlin-btn", color="primary", size="sm"),
                ], style={"marginBottom": "10px"})
            ], width=12)
        ]),
        
        dbc.Row([
            # Left sidebar: Symbol selector + controls
            dbc.Col([
                html.Div(className="dashboard-card", children=[
                    html.H5("Symbol"),
                    dcc.Dropdown(
                        id="chart-symbol-selector",
                        options=[{"label": sym, "value": sym} for sym in symbols],
                        value=symbols[0] if symbols else "AAPL",
                        clearable=False,
                        style={"color": "#000"}
                    ),
                    html.Hr(),
                    html.H5("Timeframe", style={"marginTop": "20px"}),
                    dbc.ButtonGroup([
                        dbc.Button("M1", id="tf-m1", size="sm", outline=True, color="secondary"),
                        dbc.Button("M5", id="tf-m5", size="sm", active=True, color="primary"),
                        dbc.Button("M15", id="tf-m15", size="sm", outline=True, color="secondary"),
                        dbc.Button("H1", id="tf-h1", size="sm", outline=True, color="secondary"),
                    ], vertical=True, style={"width": "100%", "marginTop": "10px"}),
                    html.Hr(),
                    html.H5("Date", style={"marginTop": "20px"}),
                    dcc.DatePickerSingle(
                        id='chart-date-picker',
                        date=datetime.now().date(),
                        display_format='YYYY-MM-DD',
                        style={"width": "100%", "marginTop": "10px"}
                    ),
                    html.P("Select trading day", className="text-muted", style={"fontSize": "0.85rem", "marginTop": "5px"}),
                    html.Hr(),
                    html.H5("Pattern Info", id="pattern-info-header", style={"marginTop": "20px"}),
                    html.Div(id="pattern-details", children=[
                        html.P("No pattern selected", className="text-muted")
                    ])
                ])
            ], width=2),
            
            # Main chart area
            dbc.Col([
                html.Div(className="dashboard-card", style={"height": "700px"}, children=[
                    dcc.Loading(
                        id="loading-chart",
                        type="default",
                        children=[
                            dcc.Graph(
                                id="candlestick-chart",
                                config=get_chart_config(),
                                style={"height": "680px"}
                            )
                        ]
                    )
                ])
            ], width=10)
        ])
    ], style={"padding": "20px"})


def get_charts_content():
    """Get charts content for callbacks."""
    return create_charts_layout()
