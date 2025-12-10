"""
Charts Tab Layout - Interactive candlestick with pattern overlay
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime

from ..components.candlestick import get_chart_config
from ..repositories import get_available_symbols


def create_charts_layout():
    """Create the Charts tab layout."""
    # Get symbols from actual parquet files (not config)
    symbols = get_available_symbols()
    
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
                dbc.Card([
                    dbc.CardBody([
                        # Active Patterns Indicator
                        html.Div([
                            html.H5("🔔 Active Patterns", style={"marginBottom": "10px"}),
                            html.Div(id="active-patterns-list", children=[
                                html.P("Loading...", className="text-muted", style={"fontSize": "0.9rem"})
                            ]),
                        ], style={"marginBottom": "15px"}),
                        
                        html.Div([
                            html.H5("📡 Live Data", style={"marginBottom": "10px", "color": "#00d26a"}),
                            html.Div(id="live-data-indicator", children=[
                                html.Div([
                                    html.Span("⚫", id="live-data-dot", className="status-dot offline"),
                                    html.Span("Checking...", id="live-data-text", style={"marginLeft": "8px", "fontSize": "0.85rem"})
                                ])
                            ]),
                            html.P(id="live-data-count", children="", className="text-muted", style={"fontSize": "0.75rem", "marginTop": "5px"})
                        ], style={"marginBottom": "15px"}),
                        
                        html.Hr(),
                        
                        # Symbol Selector
                        html.H5("Symbol"),
                        dcc.Dropdown(
                            id="chart-symbol-selector",
                            options=[{"label": sym, "value": sym} for sym in symbols],
                            value=symbols[0] if symbols else "AAPL",
                            clearable=False,
                            style={
                                "backgroundColor": "#2b2b2b",
                                "color": "#ffffff",
                                "border": "1px solid #555"
                            },
                            className="custom-dropdown"
                        ),
                        html.Hr(),
                        
                        # Market Session Toggles
                        html.H5("Market Sessions", style={"marginTop": "20px", "fontSize": "0.9rem"}),
                        dbc.Checklist(
                            options=[
                                {"label": " 📈 Pre-Market (4:00-9:30)", "value": "pre"},
                                {"label": " 🌙 After-Hours (16:00-20:00)", "value": "after"}
                            ],
                            value=[],  # Both OFF by default
                            id="market-session-toggles",
                            switch=True,
                            style={"fontSize": "0.85rem", "marginTop": "10px"}
                        ),
                        html.P("Default: Regular hours only", className="text-muted", style={"fontSize": "0.75rem", "marginTop": "5px"}),
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
                        ]),
                        html.Hr(),
                        html.H5("📁 Data Files", style={"marginTop": "20px", "fontSize": "0.9rem"}),
                        html.Div([
                            html.P([
                                html.Strong("Location: "),
                                html.Code("/traderunner/artifacts/", style={
                                    "fontSize": "0.75rem",
                                    "backgroundColor": "#1a1a1a",
                                    "padding": "2px 4px",
                                    "borderRadius": "3px"
                                })
                            ], style={"fontSize": "0.75rem", "marginBottom": "8px"}),
                            html.Div([
                                html.Span("M1: ", style={"fontWeight": "bold", "fontSize": "0.75rem"}),
                                html.Span("242 files", id="data-count-m1", style={"fontSize": "0.75rem", "color": "#00d26a"}),
                            ], style={"marginBottom": "5px"}),
                            html.Div([
                                html.Span("M5: ", style={"fontWeight": "bold", "fontSize": "0.75rem"}),
                                html.Span("259 files", id="data-count-m5", style={"fontSize": "0.75rem", "color": "#00d26a"}),
                            ], style={"marginBottom": "5px"}),
                            html.Div([
                                html.Span("M15: ", style={"fontWeight": "bold", "fontSize": "0.75rem"}),
                                html.Span("4 files", id="data-count-m15", style={"fontSize": "0.75rem", "color": "#ffa500"}),
                            ], style={"marginBottom": "8px"}),
                            html.P([
                                "📅 Dates: ",
                                html.Span("Nov 24-25, 2025", style={
                                    "color": "#00d26a",
                                    "fontWeight": "bold"
                                })
                            ], style={"fontSize": "0.75rem", "marginTop": "8px"}),
                            html.P("Place .parquet files in data_m1/, data_m5/, or data_m15/", 
                                   className="text-muted", 
                                   style={"fontSize": "0.7rem", "marginTop": "8px", "fontStyle": "italic"})                        ]),
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
