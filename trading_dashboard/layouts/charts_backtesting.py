"""
Charts - Backtesting Tab Layout
================================

Historical market data from Parquet/EODHD ONLY.

CRITICAL ARCHITECTURE RULE:
- This module MUST NOT import sqlite3 or LiveCandlesRepository
- Data source: Parquet (IntradayStore)
- Architecture tests enforce this constraint
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime, date

from trading_dashboard.repositories import get_available_symbols


def create_charts_backtesting_layout():
    """Create the Backtesting Charts tab layout."""
    
    # Get symbols from parquet files
    symbols = get_available_symbols()
    
    if not symbols:
        symbols = ['No Data']
    
    return html.Div([
        # Header
        dbc.Row([
            dbc.Col([
                html.H4("📈 Backtesting Charts", style={"color": "#4a9eff"}),
                html.P("Historical data (Parquet/EODHD)", 
                       className="text-muted", style={"fontSize": "0.9rem"}),
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button("🔄 Refresh", id="bt-refresh-btn", color="primary", size="sm"),
                    dbc.Button("🕐 NY Time", id="bt-tz-ny-btn", color="primary", size="sm"),
                    dbc.Button("🕐 Berlin Time", id="bt-tz-berlin-btn", color="secondary", size="sm", outline=True),
                ]),
            ], width=4, className="text-end"),
        ], className="mb-3"),
        
        dbc.Row([
            # Sidebar
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        # Data Source Label 
                        html.Div([
                            html.Span("📊", style={"fontSize": "1.2rem", "marginRight": "8px"}),
                            html.Strong("BACKTEST", style={"fontSize": "1.1rem", "color": "#4a9eff"}),
                            html.Br(),
                            html.Small("source: PARQUET_BACKTEST", 
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
                            id="bt-symbol-selector",
                            options=[{"label": sym, "value": sym} for sym in symbols],
                            value=symbols[0] if symbols else None,
                            clearable=False,
                            style={
                                "backgroundColor": "#2b2b2b",
                                "color": "#ffffff",
                            },
                            className="custom-dropdown mb-3"
                        ),
                        
                        # Timeframe Buttons (All timeframes)
                        html.H6("Timeframe", className="mt-3"),
                        dbc.ButtonGroup([
                            dbc.Button("M1", id="bt-tf-m1", size="sm", outline=True, color="secondary"),
                            dbc.Button("M5", id="bt-tf-m5", size="sm", active=True, color="primary"),
                            dbc.Button("M15", id="bt-tf-m15", size="sm", outline=True, color="secondary"),
                            dbc.Button("H1", id="bt-tf-h1", size="sm", outline=True, color="secondary"),
                            dbc.Button("D1", id="bt-tf-d1", size="sm", outline=True, color="secondary"),
                        ], vertical=True, style={"width": "100%"}, className="mb-3"),
                        
                        html.Hr(),
                        
                        # Date Picker (for historical analysis)
                        html.H6("Date"),
                        dcc.DatePickerSingle(
                            id="bt-date-picker",
                            date=date.today(),
                            display_format='YYYY-MM-DD',
                            style={"width": "100%"},
                            className="mb-2"
                        ),
                        html.P(
                            "Select date for historical analysis",
                            className="text-muted",
                            style={"fontSize": "0.7rem"}
                        ),
                        
                        # Window Dropdown (for D1 only)
                        html.H6("Window (D1 only)", className="mt-2"),
                        dcc.Dropdown(
                            id="bt-window-selector",
                            options=[
                                {"label": "1 Month (21 days)", "value": "1M"},
                                {"label": "3 Months (63 days)", "value": "3M"},
                                {"label": "6 Months (126 days)", "value": "6M"},
                                {"label": "12 Months (252 days)", "value": "12M"},
                                {"label": "All History", "value": "All"},
                            ],
                            value="12M",  # Default to 12 months
                            clearable=False,
                            style={
                                "backgroundColor": "#2b2b2b",
                                "color": "#ffffff",
                            },
                            className="custom-dropdown mb-2"
                        ),
                        html.P(
                            "Time window to display (ignored for intraday)",
                            className="text-muted",
                            style={"fontSize": "0.7rem"}
                        ),
                        
                        html.Hr(),
                        
                        # Session Filters (optional)
                        html.H6("Sessions"),
                        dbc.Checklist(
                            options=[
                                {"label": " Pre-Market", "value": "pre"},
                                {"label": " After-Hours", "value": "after"},
                            ],
                            value=[],  # Default: Regular hours only
                            id="bt-session-toggles",
                            switch=True,
                            style={"fontSize": "0.85rem"}
                        ),
                        
                        html.Hr(),
                        
                        # Data Availability Box
                        html.H6("📊 Data Availability", style={"fontSize": "0.9rem"}),
                        html.Div(
                            id="bt-availability-box",
                            style={
                                "fontSize": "0.72rem",
                                "padding": "8px",
                                "backgroundColor": "#1a1a1a",
                                "borderRadius": "5px",
                                "marginBottom": "8px",
                                "minHeight": "80px"
                            }
                        ),
                        dbc.Button(
                            "🔄 Refresh",
                            id="bt-availability-refresh",
                            size="sm",
                            color="secondary",
                            outline=True,
                            style={"width": "100%", "fontSize": "0.75rem"}
                        ),
                        
                        html.Hr(),
                        
                        # Info
                        html.Div([
                            html.H6("ℹ️ Backtesting Info", style={"fontSize": "0.85rem"}),
                            html.P("• Historical EODHD data", 
                                  className="text-muted", style={"fontSize": "0.75rem", "margin": "0"}),
                            html.P("• All symbols available", 
                                  className="text-muted", style={"fontSize": "0.75rem", "margin": "0"}),
                            html.P("• Full timeframe range", 
                                  className="text-muted", style={"fontSize": "0.75rem", "margin": "0"}),
                            html.P("• Date picker enabled", 
                                  className="text-muted", style={"fontSize": "0.75rem", "margin": "0"}),
                        ], style={"marginTop": "15px"}),
                    ])
                ])
            ], width=3),
            
            # Chart Area
            dbc.Col([
                dbc.Card([
                    dbc.CardBody(
                        children=[
                            dcc.Graph(
                                id="bt-candlestick-chart",
                                style={"height": "700px"},
                                config={
                                    'scrollZoom': True,  # Enable mousewheel zoom
                                    'displaylogo': False,  # Remove Plotly logo
                                    'displayModeBar': True,  # Show mode bar with zoom tools
                                }
                            )
                        ]
                    )
                ])
            ], width=9),
        ]),
    ], style={"padding": "20px"})


def get_charts_backtesting_content():
    """Get Backtesting charts content for callbacks."""
    return create_charts_backtesting_layout()
