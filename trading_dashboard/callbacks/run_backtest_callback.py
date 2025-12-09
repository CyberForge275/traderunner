"""Run Backtest Callback - Handle backtest execution from UI."""

from dash import Input, Output, State, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta


def register_run_backtest_callback(app):
    """Register callback for running backtests from the UI.
    
    This callback:
    1. Captures user inputs (strategy, symbols, timeframe, period)
    2. Triggers background backtest execution
    3. Displays progress indicator
    4. Clears run name after successful submission
    """
    
    @app.callback(
        Output("backtests-run-progress", "children"),
        Output("backtests-run-name-input", "value"),
        Output("backtests-refresh-interval", "disabled"),
        Input("backtests-run-button", "n_clicks"),
        State("backtests-new-strategy", "value"),
        State("backtests-new-symbols", "value"),
        State("backtests-new-timeframe", "value"),
        State("date-selection-mode", "value"),
        State("anchor-date", "date"),
        State("days-back", "value"),
        State("explicit-start-date", "date"),
        State("explicit-end-date", "date"),
        State("backtests-new-run-name", "value"),
        State("backtests-run-params", "value"),
        # InsideBar version management (from plugin)
        State("insidebar-version-dropdown", "value"),
        State("insidebar-new-version", "value"),
        # InsideBar strategy parameters (from plugin)
        State("insidebar-atr-period", "value"),
        State("insidebar-min-mother-bar", "value"),
        State("insidebar-breakout-confirm", "value"),
        State("insidebar-rrr", "value"),
        State("insidebar-lookback-candles", "value"),
        State("insidebar-max-pattern-age", "value"),
        State("insidebar-execution-lag", "value"),
        prevent_initial_call=True
    )
    def run_backtest(
        n_clicks,
        strategy,
        symbols_str,
        timeframe,
        date_mode,
        anchor_date,
        days_back,
        explicit_start,
        explicit_end,
        run_name,
        params_str,
        # InsideBar version
        insidebar_strategy_version,
        insidebar_new_version,
        # InsideBar parameters
        insidebar_atr_period,
        insidebar_min_mother_bar,
        insidebar_breakout_confirm,
        insidebar_rrr,
        insidebar_lookback_candles,
        insidebar_max_pattern_age,
        insidebar_execution_lag,
    ):
        """Execute backtest in background and show progress."""
        from ..services.backtest_service import get_backtest_service
        from datetime import datetime
        
        if not n_clicks:
            return "", "", True
        
        # Validate run name is provided
        if not run_name or not run_name.strip():
            error_msg = html.Div(
                "❌ Please enter a name for this backtest run",
                style={"color": "red", "fontWeight": "bold"}
            )
            return error_msg, run_name, True
        
        # Prepend timestamp to run name
        timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
        run_name = f"{timestamp}_{run_name.strip()}"
        
        # CRITICAL: Validate version is provided (mandatory for strategy lab progression)
        import re
        version_to_use = None
        
        # Check if strategy supports versioning
        if strategy in ["insidebar_intraday", "insidebar_intraday_v2"]:
            # First check if new version provided
            if insidebar_new_version and insidebar_new_version.strip():
                # Validate format
                pattern = r'^v\d+\.\d{2}$'
                if re.match(pattern, insidebar_new_version.strip()):
                    version_to_use = insidebar_new_version.strip()
                else:
                    error_msg = html.Div([
                        html.Span("❌ Invalid version format. ", style={"color": "red", "fontWeight": "bold"}),
                        html.Span(f"Use pattern v#.## (e.g., v1.01, v2.00). You entered: '{insidebar_new_version}'"),
                    ])
                    return error_msg, run_name, True
            elif insidebar_strategy_version:
                # Use selected version from dropdown
                version_to_use = insidebar_strategy_version
            else:
                # NO VERSION PROVIDED - Block execution
                error_msg = html.Div([
                    html.Span("❌ Version required. ", style={"color": "red", "fontWeight": "bold"}),
                    html.Br(),
                    html.Span("Select an existing version from dropdown OR enter a new version (e.g., v1.01)", 
                             style={"fontSize": "0.9em"}),
                ], style={"padding": "8px", "backgroundColor": "#ffebee", "borderLeft": "3px solid red"})
                return error_msg, run_name, True
        
        # Validate inputs
        if not strategy or not symbols_str or not timeframe:
            return html.Div("❌ Please select strategy, symbols, and timeframe", style={"color": "red"}), run_name, True
        
        # Validate symbols
        if not symbols_str or not symbols_str.strip():
            error_msg = html.Div([
                html.Span("⚠️ ", style={"color": "var(--accent-yellow)"}),
                html.Span("Error: Please enter at least one symbol"),
            ])
            return error_msg, run_name, True
        
        symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
        
        if not symbols:
            error_msg = html.Div([
                html.Span("⚠️ ", style={"color": "var(--accent-yellow)"}),
                html.Span("Error: Please enter at least one symbol"),
            ])
            return error_msg, run_name, True
        
        # Parse params string if provided (legacy)
        config_params = {}
        if params_str:
            try:
                for item in params_str.split(','):
                    if '=' in item:
                        k, v = item.split('=', 1)
                        config_params[k.strip()] = v.strip()
            except Exception:
                pass
        
        # Calculate start/end dates based on mode
        if date_mode == "days_back":
            # Calculate from anchor date and days back
            if isinstance(anchor_date, str):
                end_date = datetime.fromisoformat(anchor_date).date()
            else:
                end_date = anchor_date
            
            start_date = end_date - timedelta(days=int(days_back or 30))
        else:  # explicit mode
            # Use explicit dates
            if isinstance(explicit_start, str):
                start_date = datetime.fromisoformat(explicit_start).date()
            else:
                start_date = explicit_start
            
            if isinstance(explicit_end, str):
                end_date = datetime.fromisoformat(explicit_end).date()
            else:
                end_date = explicit_end
        
        # Start backtest in background
        service = get_backtest_service()
        
        # Convert dates to strings for service
        start_date_str = start_date.isoformat() if start_date else None
        end_date_str = end_date.isoformat() if end_date else None
        
        # Build strategy parameters dict from UI inputs
        strategy_params = {}
        if strategy in ["insidebar_intraday", "insidebar_intraday_v2"]:
            strategy_params = {
                "atr_period": insidebar_atr_period or 14,
                "min_mother_bar_size": insidebar_min_mother_bar or 0.5,
                "breakout_confirmation": bool(insidebar_breakout_confirm and "true" in insidebar_breakout_confirm),
                "risk_reward_ratio": insidebar_rrr or 2.0,
                "lookback_candles": insidebar_lookback_candles or 50,
                "max_pattern_age_candles": insidebar_max_pattern_age or 12,
                "execution_lag": insidebar_execution_lag or 0,
            }
        
        job_id = service.start_backtest(
            run_name=run_name,
            strategy=strategy,
            symbols=symbols,
            timeframe=timeframe,
            start_date=start_date_str,
            end_date=end_date_str,
            config_params=config_params if config_params else None,
        )
        
        # Format date range for display
        date_range_display = f"{start_date_str} to {end_date_str}" if start_date_str and end_date_str else "N/A"
        
        # Show progress indicator
        progress_msg = html.Div(
            [
                html.Div("🚀 Backtest started!", style={"color": "green", "fontWeight": "bold"}),
                html.Div(f"Run: {run_name}", style={"fontSize": "0.85em", "marginTop": "4px"}),
                html.Div(f"Job ID: {job_id}", style={"fontSize": "0.85em"}),
            ]
        )
        
        # Enable refresh interval to poll for completion
        # Clear run name input for next run
        return progress_msg, "", False
    
    @app.callback(
        Output("backtests-run-progress", "children", allow_duplicate=True),
        Output("backtests-refresh-interval", "disabled", allow_duplicate=True),
        Input("backtests-refresh-interval", "n_intervals"),
        prevent_initial_call=True
    )
    def check_job_status(n_intervals):
        """Poll for job status and update progress indicator."""
        from ..services.backtest_service import get_backtest_service
        
        service = get_backtest_service()
        all_jobs = service.get_all_jobs()
        
        # Check if there are any running jobs
        running_jobs = {jid: j for jid, j in all_jobs.items() if j.get("status") == "running"}
        
        # Also show recently completed/failed jobs (last 30 seconds)
        recent_jobs = {}
        import time
        current_time = time.time()
        for jid, job in all_jobs.items():
            if job.get("status") in ["completed", "failed"]:
                # Check if completed/failed recently
                ended_at = job.get("ended_at")
                if ended_at:
                    try:
                        from datetime import datetime
                        end_time = datetime.fromisoformat(ended_at).timestamp()
                        if current_time - end_time < 30:  # Show for 30 seconds
                            recent_jobs[jid] = job
                    except:
                        pass
        
        if not running_jobs and not recent_jobs:
            # No jobs to display - clear progress
            return "", True
        
        # Show status of all relevant jobs
        job_statuses = []
        
        # Running jobs
        for job_id, job in running_jobs.items():
            progress_text = job.get("progress", "Running...")
            run_name = job.get("run_name", "unknown")
            started_at = job.get("started_at", "")
            
            job_statuses.append(
                html.Div([
                    html.Div(
                        dbc.Spinner(size="sm", color="success", spinner_style={"marginRight": "8px"}),
                        style={"display": "inline-block"},
                    ),
                    html.Div([
                        html.Div(f"🚀 Running: {run_name}", style={"fontWeight": "bold", "color": "var(--accent-green)"}),
                        html.Div(f"Job ID: {job_id}", style={"fontSize": "0.75em", "color": "var(--text-secondary)", "marginTop": "2px"}),
                        html.Div(f"Status: {progress_text}", style={"fontSize": "0.85em", "marginTop": "4px", "fontStyle": "italic"}),
                        html.Div(f"Started: {started_at[:19] if started_at else 'N/A'}", style={"fontSize": "0.75em", "color": "var(--text-secondary)", "marginTop": "2px"}),
                    ]),
                ], style={"marginBottom": "12px"})
            )
        
        # Recently completed jobs
        for job_id, job in recent_jobs.items():
            run_name = job.get("run_name", "unknown")
            status = job.get("status")
            progress_text = job.get("progress", "")
            ended_at = job.get("ended_at", "")
            traceback_text = job.get("traceback", None)
            
            if status == "completed":
                icon = "✅"
                color = "var(--accent-green)"
                status_text = "Completed Successfully"
                details = []
            else:  # failed
                # Failed job - show detailed error with traceback
                error_msg = job.get("error", "Unknown error")
                traceback_text = job.get("traceback", "No traceback available")
                
                # Also include command output if available (from run_log.json)
                command_output = ""
                if "output" in job and job["output"]:
                    command_output = f"\n\n### Command Output:\n```\n{job['output']}\n```"
                
                progress_display = html.Div([
                    dbc.Alert([
                        html.H5("Failed", className="alert-heading mb-2"),
                        html.P(f"Error: {error_msg}", className="mb-2"),
                        html.Small([
                            html.Strong("Job ID: "), job_id, html.Br(),
                            html.Strong("Ended: "), job.get("ended_at", "Unknown")
                        ], className="text-muted")
                    ], color="danger", className="mb-3"),
                    
                    # Expandable traceback section
                    dbc.Card([
                        dbc.CardHeader(
                            dbc.Button(
                                "📋 Full Error Traceback",
                                id={"type": "error-collapse-btn", "index": job_id},
                                className="w-100 text-start",
                                color="link",
                                size="sm"
                            )
                        ),
                        dbc.Collapse(
                            dbc.CardBody([
                                html.Pre(traceback_text, style={"fontSize": "0.85em", "whiteSpace": "pre-wrap"}),
                                html.Div(dcc.Markdown(command_output)) if command_output else None
                            ]),
                            id={"type": "error-collapse", "index": job_id},
                            is_open=False
                        )
                    ], className="border-danger")
                ])
                job_statuses.append(progress_display)
                continue # Skip the common display logic below for failed jobs
            
            job_statuses.append(
                html.Div([
                    html.Div(icon, style={"fontSize": "1.2em", "marginRight": "8px", "display": "inline-block"}),
                    html.Div([
                        html.Div(f"{run_name}", style={"fontWeight": "bold", "color": color}),
                        html.Div(f"{status_text}", style={"fontSize": "0.85em", "marginTop": "2px"}),
                        html.Div(f"Ended: {ended_at[:19] if ended_at else 'N/A'}", style={"fontSize": "0.75em", "color": "var(--text-secondary)", "marginTop": "2px"}),
                        *details,  # Add traceback if present
                    ], style={"display": "inline-block", "verticalAlign": "top"}),
                ], style={"marginBottom": "12px"})
            )
        
        return html.Div(job_statuses), len(running_jobs) == 0
