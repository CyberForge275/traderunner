"""
Portfolio Tab Layout - Position tracking and P&L
"""
from dash import html, dash_table
import dash_bootstrap_components as dbc
import pandas as pd

from ..repositories import get_portfolio_summary


def create_portfolio_card_large(portfolio: dict):
    """Create large portfolio value card."""
    pnl = portfolio.get("daily_pnl", 0)
    pnl_pct = portfolio.get("daily_pnl_pct", 0)
    pnl_class = "pnl-positive" if pnl >= 0 else "pnl-negative"
    pnl_sign = "+" if pnl >= 0 else ""
    
    return html.Div(
        className="dashboard-card",
        children=[
            html.H4("Portfolio Value", style={"marginBottom": "20px"}),
            html.Div(
                f"${portfolio.get('total_value', 0):,.2f}",
                style={
                    "fontSize": "3rem",
                    "fontWeight": "700",
                    "color": "var(--text-primary)",
                    "marginBottom": "10px"
                }
            ),
            dbc.Row([
                dbc.Col([
                    html.Div("Cash", style={"color": "var(--text-secondary)", "fontSize": "0.875rem"}),
                    html.Div(f"${portfolio.get('cash', 0):,.2f}", style={"fontSize": "1.25rem", "fontWeight": "500"})
                ]),
                dbc.Col([
                    html.Div("Positions", style={"color": "var(--text-secondary)", "fontSize": "0.875rem"}),
                    html.Div(f"${portfolio.get('positions_value', 0):,.2f}", style={"fontSize": "1.25rem", "fontWeight": "500"})
                ]),
                dbc.Col([
                    html.Div("Daily P&L", style={"color": "var(--text-secondary)", "fontSize": "0.875rem"}),
                    html.Div(
                        f"{pnl_sign}${abs(pnl):,.2f} ({pnl_sign}{pnl_pct:.2f}%)",
                        className=pnl_class,
                        style={"fontSize": "1.25rem", "fontWeight": "500"}
                    )
                ])
            ])
        ]
    )


def create_positions_table(positions: list):
    """Create positions table."""
    if not positions:
        return html.Div(
            className="dashboard-card",
            children=[
                html.H5("Open Positions"),
                html.P("No open positions", className="text-muted", style={"padding": "20px"})
            ]
        )
    
    df = pd.DataFrame(positions)
    
    return html.Div(
        className="dashboard-card",
        children=[
            html.H5("Open Positions"),
            dash_table.DataTable(
                id='positions-table',
                columns=[
                    {"name": "Symbol", "id": "symbol"},
                    {"name": "Qty", "id": "quantity"},
                    {"name": "Avg Price", "id": "avg_price", "type": "numeric", "format": {"specifier": "$.2f"}},
                    {"name": "Current Price", "id": "current_price", "type": "numeric", "format": {"specifier": "$.2f"}},
                    {"name": "Unrealized P&L", "id": "unrealized_pnl", "type": "numeric", "format": {"specifier": "$.2f"}},
                    {"name": "Side", "id": "side"},
                ],
                data=df.to_dict('records'),
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
                        'if': {'column_id': 'unrealized_pnl', 'filter_query': '{unrealized_pnl} > 0'},
                        'color': 'var(--accent-green)'
                    },
                    {
                        'if': {'column_id': 'unrealized_pnl', 'filter_query': '{unrealized_pnl} < 0'},
                        'color': 'var(--accent-red)'
                    }
                ]
            )
        ]
    )


def create_portfolio_layout():
    """Create the Portfolio tab layout."""
    portfolio = get_portfolio_summary()
    positions = portfolio.get("positions", [])
    
    return html.Div([
        dbc.Row([
            dbc.Col([
                create_portfolio_card_large(portfolio)
            ], width=12)
        ]),
        dbc.Row([
            dbc.Col([
                create_positions_table(positions)
            ], width=12)
        ], style={"marginTop": "20px"})
    ], style={"padding": "20px"})


def get_portfolio_content():
    """Get portfolio content for callbacks."""
    return create_portfolio_layout()
