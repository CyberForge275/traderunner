"""
History Tab Layout - Trading event timeline with date filtering
"""
from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta

from ..repositories.history import get_events_by_date, get_daily_statistics


def create_statistics_cards(stats: dict):
    """Create statistics summary cards."""
    return dbc.Row([
        dbc.Col([
            html.Div(className="dashboard-card text-center", children=[
                html.H6("Patterns Detected", style={"color": "var(--text-secondary)", "marginBottom": "5px"}),
                html.H3(str(stats.get('total_patterns', 0)), style={"marginBottom": "0"})
            ])
        ], width=3),
        dbc.Col([
            html.Div(className="dashboard-card text-center", children=[
                html.H6("Patterns Triggered", style={"color": "var(--text-secondary)", "marginBottom": "5px"}),
                html.H3(str(stats.get('patterns_triggered', 0)), style={"marginBottom": "0", "color": "var(--accent-green)"})
            ])
        ], width=3),
        dbc.Col([
            html.Div(className="dashboard-card text-center", children=[
                html.H6("Orders Created", style={"color": "var(--text-secondary)", "marginBottom": "5px"}),
                html.H3(str(stats.get('total_orders', 0)), style={"marginBottom": "0"})
            ])
        ], width=3),
        dbc.Col([
            html.Div(className="dashboard-card text-center", children=[
                html.H6("Orders Filled", style={"color": "var(--text-secondary)", "marginBottom": "5px"}),
                html.H3(str(stats.get('orders_filled', 0)), style={"marginBottom": "0", "color": "var(--accent-blue)"})
            ])
        ], width=3)
    ], style={"marginBottom": "20px"})


def create_event_timeline(events_df):
    """Create event timeline table."""
    if events_df.empty:
        return html.Div(
            className="dashboard-card",
            children=[
                html.H5("Event Timeline"),
                html.P("No events found for selected date range", className="text-muted", style={"padding": "40px"})
            ]
        )
    
    # Format timestamp for display
    events_df['timestamp_display'] = events_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    return html.Div(
        className="dashboard-card",
        children=[
            html.H5("Event Timeline", style={"marginBottom": "15px"}),
            dash_table.DataTable(
                id='events-table',
                columns=[
                    {"name": "Time", "id": "timestamp_display"},
                    {"name": "Event", "id": "event_type"},
                    {"name": "Symbol", "id": "symbol"},
                    {"name": "Details", "id": "details"},
                    {"name": "Status", "id": "status"},
                ],
                data=events_df[['timestamp_display', 'event_type', 'symbol', 'details', 'status']].to_dict('records'),
                page_size=50,
                style_table={'overflowX': 'auto'},
                style_header={
                    'backgroundColor': 'var(--bg-secondary)',
                    'color': 'var(--text-secondary)',
                    'fontWeight': 'bold',
                    'border': '1px solid var(--border-color)'
                },
                style_cell={
                    'backgroundColor': 'var(--bg-card)',
                    'color': 'var(--text-primary)',
                    'border': '1px solid var(--border-color)',
                    'textAlign': 'left',
                    'padding': '10px'
                },
                style_data_conditional=[
                    {
                        'if': {'column_id': 'event_type', 'filter_query': '{event_type} = "pattern_detected"'},
                        'color': 'var(--accent-yellow)'
                    },
                    {
                        'if': {'column_id': 'event_type', 'filter_query': '{event_type} = "order_intent"'},
                        'color': 'var(--accent-blue)'
                    },
                    {
                        'if': {'column_id': 'status', 'filter_query': '{status} = "filled"'},
                        'color': 'var(--accent-green)'
                    },
                    {
                        'if': {'column_id': 'status', 'filter_query': '{status} = "rejected"'},
                        'color': 'var(--accent-red)'
                    }
                ]
            )
        ]
    )


def create_history_layout():
    """Create the History tab layout."""
    # Default to today
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Get initial data
    events = get_events_by_date(yesterday, today)
    stats = get_daily_statistics(today)
    
    return html.Div([
        # Controls row
        dbc.Row([
            dbc.Col([
                html.Div(className="dashboard-card", children=[
                    html.H6("Date Range", style={"marginBottom": "10px"}),
                    dcc.DatePickerRange(
                        id='date-picker-range',
                        start_date=yesterday,
                        end_date=today,
                        display_format='YYYY-MM-DD',
                        style={'width': '100%'}
                    )
                ])
            ], width=4),
            dbc.Col([
                html.Div(className="dashboard-card", children=[
                    html.H6("Symbol Filter", style={"marginBottom": "10px"}),
                    dcc.Dropdown(
                        id='history-symbol-filter',
                        options=[
                            {'label': 'All Symbols', 'value': 'all'},
                            {'label': 'AAPL', 'value': 'AAPL'},
                            {'label': 'MSFT', 'value': 'MSFT'},
                            {'label': 'TSLA', 'value': 'TSLA'},
                        ],
                        value='all',
                        clearable=False,
                        style={"color": "#000"}
                    )
                ])
            ], width=3),
            dbc.Col([
                html.Div(className="dashboard-card", children=[
                    html.H6("Status Filter", style={"marginBottom": "10px"}),
                    dcc.Dropdown(
                        id='history-status-filter',
                        options=[
                            {'label': 'All Status', 'value': 'all'},
                            {'label': 'Pending', 'value': 'pending'},
                            {'label': 'Triggered', 'value': 'triggered'},
                            {'label': 'Filled', 'value': 'filled'},
                            {'label': 'Rejected', 'value': 'rejected'},
                        ],
                        value='all',
                        clearable=False,
                        style={"color": "#000"}
                    )
                ])
            ], width=3),
            dbc.Col([
                html.Div(className="dashboard-card text-center", children=[
                    html.H6("Export", style={"marginBottom": "10px"}),
                    dbc.Button("📥 Download CSV", id="export-csv-btn", color="success", size="sm")
                ])
            ], width=2)
        ], style={"marginBottom": "20px"}),
        
        # Statistics cards
        html.Div(id="history-stats", children=create_statistics_cards(stats)),
        
        # Event timeline
        html.Div(id="history-timeline", children=create_event_timeline(events)),
        
        # Hidden download component
        dcc.Download(id="download-csv")
        
    ], style={"padding": "20px"})


def get_history_content():
    """Get history content for callbacks."""
    return create_history_layout()
