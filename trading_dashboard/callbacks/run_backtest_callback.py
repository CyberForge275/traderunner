"""Run Backtest Callback - Handle backtest execution from UI."""

from dash import Input, Output, State, html
import dash_bootstrap_components as dbc
from datetime import datetime


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
        State("backtests-new-period", "value"),
        State("backtests-run-name-input", "value"),
        State("backtests-run-params", "value"),
        prevent_initial_call=True
    )
    def run_backtest(
        n_clicks,
        strategy,
        symbols_str,
        timeframe,
        period,
        run_name,
        params_str
    ):
        """Execute backtest in background and show progress."""
        from ..services.backtest_service import get_backtest_service
        
        if not n_clicks:
            return "", "", True
        
        # Generate run name if not provided
        if not run_name or not run_name.strip():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = f"run_{strategy}_{timestamp}"
        else:
            run_name = run_name.strip()
        
        # Parse symbols
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
        
        # Parse additional params (simple key=value format)
        config_params = {}
        if params_str and params_str.strip():
            try:
                for line in params_str.strip().split("\\n"):
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        # Try to evaluate as number or keep as string
                        try:
                            # Try int first
                            config_params[key] = int(val)
                        except ValueError:
                            try:
                                # Try float
                                config_params[key] = float(val)
                            except ValueError:
                                # Keep as string
                                config_params[key] = val
            except Exception as e:
                # Ignore parse errors, just log
                pass
        
        # Start backtest in background
        service = get_backtest_service()
        job_id = service.start_backtest(
            run_name=run_name,
            strategy=strategy,
            symbols=symbols,
            timeframe=timeframe,
            period=period,
            config_params=config_params if config_params else None
        )
        
        # Show progress indicator
        progress = html.Div([
            html.Div(
                dbc.Spinner(size="sm", color="success", spinner_style={"marginRight": "8px"}),
                style={"display": "inline-block"},
            ),
            html.Div([
                html.Div(f"🚀 Running: {run_name}", style={"fontWeight": "bold", "color": "var(--accent-green)"}),
                html.Div(f"Job ID: {job_id}", style={"fontSize": "0.85em", "color": "var(--text-secondary)", "marginTop": "4px"}),
                html.Div(f"Strategy: {strategy} | {timeframe} | {period}", style={"fontSize": "0.85em", "color": "var(--text-secondary)"}),
                html.Div(f"Symbols: {', '.join(symbols)}", style={"fontSize": "0.85em", "color": "var(--text-secondary)"}),
            ]),
        ])
        
        # Enable refresh interval to poll for completion
        # Clear run name input for next run
        return progress, "", False
    
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
        
        if not running_jobs:
            # No running jobs - disable interval and clear progress
            return "", True
        
        # Show status of running jobs
        job_statuses = []
        for job_id, job in running_jobs.items():
            progress_msg = job.get("progress", "Running...")
            run_name = job.get("run_name", "unknown")
            job_statuses.append(
                html.Div([
                    html.Div(
                        dbc.Spinner(size="sm", color="success", spinner_style={"marginRight": "8px"}),
                        style={"display": "inline-block"},
                    ),
                    html.Div([
                        html.Div(f"🚀 {run_name}", style={"fontWeight": "bold", "color": "var(--accent-green)"}),
                        html.Div(progress_msg, style={"fontSize": "0.85em", "color": "var(--text-secondary)", "marginTop": "4px"}),
                    ]),
                ], style={"marginBottom": "10px"})
            )
        
        # Keep interval enabled
        return html.Div(job_statuses), False
