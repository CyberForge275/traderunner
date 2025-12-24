"""
Helper function to build run history panel for Pre-Paper tab.
This is used internally by pre_papertrade_callbacks.py
"""

from dash import html, dash_table
import dash_bootstrap_components as dbc

from trading_dashboard.utils.run_history_utils import (
    get_pre_paper_run_history,
    format_run_history_for_table
)


def build_run_history_panel(strategy_key: str):
    """
    Build run history panel for displaying strategy run history.
    
    Args:
        strategy_key: Strategy identifier (e.g., "insidebar_intraday")
        
    Returns:
        Dash component (dbc.Card) or empty list if no data
    """
    # Only show for InsideBar strategy (MVP scope)
    if strategy_key != "insidebar_intraday":
        return []
    
    try:
        # Fetch run history
        runs = get_pre_paper_run_history(strategy_key, limit=10)
        
        if not runs:
            # No runs yet
            return dbc.Card(
                [
                    dbc.CardHeader("📜 Run History (InsideBar Pre-Paper)"),
                    dbc.CardBody(
                        [
                            html.P(
                                "No Pre-PaperTrading runs found for this strategy version.",
                                className="text-muted mb-0"
                            )
                        ]
                    ),
                ],
                className="mt-3"
            )
        
        # Format for table
        table_data = format_run_history_for_table(runs)
        
        # Build panel
        return dbc.Card(
            [
                dbc.CardHeader("📜 Run History (InsideBar Pre-Paper - Last 10 Runs)"),
                dbc.CardBody(
                    [
                        dash_table.DataTable(
                            id="run-history-table",
                            columns=[
                                {"name": col, "id": col}
                                for col in table_data[0].keys()
                            ] if table_data else [],
                            data=table_data,
                            page_size=10,
                            style_table={"overflowX": "auto"},
                            style_cell={
                                "textAlign": "left",
                                "padding": "8px",
                                "fontSize": "12px",
                            },
                            style_header={
                                "fontWeight": "bold",
                                "backgroundColor": "#e9ecef",
                                "color": "#212529",
                                "border": "1px solid #dee2e6"
                            },
                            style_data={
                                "border": "1px solid #dee2e6"
                            },
                            # Remove aggressive row coloring - use subtle hover instead
                            style_data_conditional=[
                                {
                                    # Subtle hover effect
                                    "if": {"state": "active"},
                                    "backgroundColor": "#f8f9fa",
                                },
                            ],
                        ),
                    ]
                ),
            ],
            className="mt-3"
        )
    
    except Exception as e:
        # Error building panel - show error message
        return dbc.Card(
            [
                dbc.CardHeader("📜 Run History"),
                dbc.CardBody(
                    [
                        html.P(
                            f"Error loading run history: {str(e)}",
                            className="text-danger mb-0"
                        )
                    ]
                ),
            ],
            className="mt-3"
        )
