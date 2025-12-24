"""
Run Summary Utilities for Pre-PaperTrading Lab
===============================================

Helper functions to build comprehensive run summary displays showing:
- Run setup (strategy, mode, symbols, timeframe, etc.)
- Lifecycle metadata (version, run ID, environment)
- Technical details (metrics, tags, config)
"""

import json
from typing import Dict, Optional, Any
from dash import html
import dash_bootstrap_components as dbc


def build_run_summary(
    result: Dict,
    strategy: str,
    mode: str,
    symbols_str: str,
    timeframe: str,
    replay_date: Optional[str] = None,
    session_filter_input: Optional[str] = None,
    show_technical_details: bool = True
) -> list:
    """
    Build comprehensive run summary for display in Pre-Paper tab.
    
    Args:
        result: Result dict from execute_strategy (contains strategy_version, strategy_run_id, etc.)
        strategy: Strategy selection from dropdown
        mode: "replay" or "live"
        symbols_str: Comma-separated symbols
        timeframe: Selected timeframe
        replay_date: Date for replay mode (optional)
        session_filter_input: Session hours filter (optional)
        show_technical_details: Whether to include expandable technical section
        
    Returns:
        List of Dash components for run summary display
    """
    components = []
    
    # Extract strategy name (remove version suffix if present)
    strategy_name = strategy.split("|")[0] if "|" in strategy else strategy
    
    # Parse symbols
    symbols_list = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    symbols_display = ", ".join(symbols_list) if symbols_list else "None"
    
    # Session hours display
    session_display = session_filter_input if session_filter_input and session_filter_input.strip() else "All sessions"
    
    # Determine lab designation
    if mode == "replay":
        lab_display = "Pre-Paper (Time Machine)"
        mode_display = f"Replay – Past Day ({replay_date})" if replay_date else "Replay – Past Day"
    else:
        lab_display = "Pre-Paper (Live)"
        mode_display = "Live (Real-time)"
    
    # Build run setup grid
    components.append(
        html.Div([
            html.H6("📊 Run Setup", className="mt-3 mb-2 text-primary"),
            dbc.Row([
                dbc.Col([
                    html.Strong("Lab:"),
                    html.Span(f" {lab_display}", className="ms-1")
                ], width=6, className="mb-1"),
                dbc.Col([
                    html.Strong("Mode:"),
                    html.Span(f" {mode_display}", className="ms-1")
                ], width=6, className="mb-1"),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Strong("Symbols:"),
                    html.Span(f" {symbols_display}", className="ms-1")
                ], width=6, className="mb-1"),
                dbc.Col([
                    html.Strong("Timeframe:"),
                    html.Span(f" {timeframe}", className="ms-1")
                ], width=6, className="mb-1"),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Strong("Session Hours:"),
                    html.Span(f" {session_display}", className="ms-1")
                ], width=12, className="mb-1"),
            ]),
        ], className="p-3 bg-light rounded")
    )
    
    # Add lifecycle metadata if available
    if "strategy_version" in result or "strategy_run_id" in result:
        lifecycle_rows = []
        
        if "strategy_version" in result:
            v = result["strategy_version"]
            lifecycle_rows.append(
                dbc.Row([
                    dbc.Col([
                        html.Strong("Strategy Version:"),
                        html.Span(f" {v.get('label', 'N/A')}", className="ms-1")
                    ], width=12, className="mb-1"),
                ])
            )
            lifecycle_rows.append(
                dbc.Row([
                    dbc.Col([
                        html.Strong("Version Details:"),
                        html.Span(
                            f" {v.get('strategy_key', 'N/A')} (impl={v.get('impl_version', 'N/A')}, "
                            f"ID={v.get('id', 'N/A')}, Stage={v.get('lifecycle_stage', 'N/A')})",
                            className="ms-1 text-muted small"
                        )
                    ], width=12, className="mb-1"),
                ])
            )
        
        if "strategy_run_id" in result:
            run_id = result["strategy_run_id"]
            # Get environment from result if available
            environment = result.get("environment", "N/A")
            
            lifecycle_rows.append(
                dbc.Row([
                    dbc.Col([
                        html.Strong("Run ID:"),
                        html.Span(f" {run_id}", className="ms-1")
                    ], width=6, className="mb-1"),
                    dbc.Col([
                        html.Strong("Environment:"),
                        html.Span(f" {environment}", className="ms-1")
                    ], width=6, className="mb-1"),
                ])
            )
        
        # Get duration if available
        if "duration_seconds" in result:
            lifecycle_rows.append(
                dbc.Row([
                    dbc.Col([
                        html.Strong("Duration:"),
                        html.Span(f" {result['duration_seconds']:.2f}s", className="ms-1")
                    ], width=6, className="mb-1"),
                ])
            )
        
        components.append(
            html.Div([
                html.H6("🔖 Lifecycle Metadata", className="mt-3 mb-2 text-info"),
                *lifecycle_rows
            ], className="p-3 bg-light rounded mt-2")
        )
    
    # Add technical details (expandable)
    if show_technical_details and ("strategy_run_id" in result or "strategy_version" in result):
        technical_content = []
        
        # Add raw data if available
        if "strategy_version" in result:
            v = result["strategy_version"]
            technical_content.append(
                html.Div([
                    html.Strong("Config Hash: "),
                    html.Code(v.get("config_hash", "N/A"), className="ms-1")
                ], className="mb-1")
            )
            technical_content.append(
                html.Div([
                    html.Strong("Code Ref: "),
                    html.Code(v.get("code_ref", "N/A"), className="ms-1")
                ], className="mb-1")
            )
        
        # Add metrics if available
        if "metrics_summary" in result:
            technical_content.append(
                html.Div([
                    html.Strong("Metrics Summary: "),
                    html.Pre(
                        json.dumps(result["metrics_summary"], indent=2),
                        className="mt-1 p-2 bg-white border rounded",
                        style={"fontSize": "11px", "maxHeight": "200px", "overflow": "auto"}
                    )
                ], className="mb-1")
            )
        
        components.append(
            dbc.Card([
                dbc.CardHeader(
                    dbc.Button(
                        [html.I(className="bi bi-code-slash me-2"), "Technical Details"],
                        id="technical-details-toggle",
                        className="btn-sm btn-link text-decoration-none p-0",
                        color="link",
                        n_clicks=0
                    )
                ),
                dbc.Collapse(
                    dbc.CardBody(technical_content if technical_content else [
                        html.P("No technical details available.", className="text-muted mb-0")
                    ]),
                    id="technical-details-collapse",
                    is_open=False
                )
            ], className="mt-2")
        )
    
    return components


def format_strategy_display_name(strategy_value: str) -> str:
    """
    Format strategy value for user-friendly display.
    
    Handles both simple strategy keys and compound "strategy|version" values.
    
    Args:
        strategy_value: Value from dropdown (e.g., "insidebar_intraday" or "strategy|v1.00")
        
    Returns:
        Human-readable strategy name
    """
    # Strategy name mappings
    strategy_names = {
        "insidebar_intraday": "InsideBar Intraday",
        "insidebar_intraday_v2": "InsideBar Intraday v2",
        "rudometkin_moc_mode": "Rudometkin MOC",
    }
    
    # Extract base strategy key
    base_key = strategy_value.split("|")[0] if "|" in strategy_value else strategy_value
    
    # Get display name
    display_name = strategy_names.get(base_key, base_key.replace("_", " ").title())
    
    # Add version suffix if present
    if "|" in strategy_value:
        version = strategy_value.split("|")[1]
        display_name = f"{display_name} ({version})"
    
    return display_name
