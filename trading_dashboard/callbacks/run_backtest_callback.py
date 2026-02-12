"""Run Backtest Callback - Handle backtest execution from UI."""

from dash import Input, Output, State, html, dcc
import logging
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from ..ui_ids import Nav, BT, RUN


logger = logging.getLogger(__name__)

try:
    from axiom_bt.utils.trace import trace_ui
except ModuleNotFoundError:
    logger.warning("trace_ui unavailable; continuing without tracing")

    def trace_ui(*args, **kwargs):
        return None


def register_run_backtest_callback(app):
    """Register callback for running backtests from the UI.

    This callback:
    1. Captures user inputs (strategy, symbols, timeframe, period)
    2. Triggers background backtest execution
    3. Displays progress indicator
    4. Clears run name after successful submission
    """

    @app.callback(
        Output(RUN.PROGRESS_CONTAINER, "children", allow_duplicate=True),
        Output(RUN.RUN_NAME_INPUT, "value"),
        Output("nav:refresh-policy", "data"),
        Output(RUN.PIPELINE_LOG, "children", allow_duplicate=True),
        Output(RUN.CURRENT_JOB_ID_STORE, "data"),
        Output(BT.RUN_STATUS_ICON, "children", allow_duplicate=True),
        Input(RUN.START_BUTTON, "n_clicks"),
        State(RUN.STRATEGY_DROPDOWN, "value"),
        State(RUN.VERSION_DROPDOWN, "value"),
        State(RUN.SYMBOL_INPUT, "value"),
        State(RUN.TIMEFRAME_DROPDOWN, "value"),
        State(RUN.DATE_MODE_RADIO, "value"),
        State(RUN.ANCHOR_DATE_PICKER, "date"),
        State(RUN.DAYS_BACK_INPUT, "value"),
        State(RUN.EXPLICIT_START_PICKER, "date"),
        State(RUN.EXPLICIT_END_PICKER, "date"),
        State(RUN.RUN_NAME_INPUT, "value"),
        State(RUN.CONFIG_STORE, "data"),            # SSOT Snapshot
        State(RUN.COMPOUND_TOGGLE, "value"),
        State(RUN.EQUITY_BASIS_DROPDOWN, "value"),
        prevent_initial_call=True
    )
    def run_backtest(
        n_clicks,
        strategy,
        selected_version,
        symbols_str,
        timeframe,
        date_mode,
        anchor_date,
        days_back,
        explicit_start,
        explicit_end,
        run_name,
        bt_config_snapshot,  # SSOT Snapshot from bt-config-store
        compound_toggle_val,
        equity_basis_val,
    ):
        """Execute backtest in background and show progress."""
        from ..services.backtest_service import get_backtest_service
        from datetime import datetime

        if not n_clicks:
            return "", "", {"bt_job_running": False}, "", None, ""

        # Validate run name is provided
        if not run_name or not run_name.strip():
            error_msg = html.Div(
                "❌ Please enter a name for this backtest run",
                style={"color": "red", "fontWeight": "bold"}
            )
            return error_msg, run_name, {"bt_job_running": False}, "", None, ""

        # Prepend timestamp to run name
        timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
        run_name = f"{timestamp}_{run_name.strip()}"
        trace_ui(
            step="ui_callback_entry",
            run_id=run_name,
            strategy_id=strategy,
            file=__file__,
            func="run_backtest",
        )

        # CRITICAL: Validate version is provided (mandatory for strategy lab progression)
        import re
        version_to_use = None

        # SSOT: Logic for migrated strategies (InsideBar)
        if strategy == "insidebar_intraday":
            if not bt_config_snapshot or bt_config_snapshot.get("strategy_id") != strategy:
                if selected_version:
                    try:
                        from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore
                        defaults = StrategyConfigStore.get_defaults(strategy, selected_version)
                        bt_config_snapshot = {
                            "strategy_id": strategy,
                            "version": selected_version,
                            "required_warmup_bars": defaults.get("required_warmup_bars", 0),
                            "core": defaults.get("core", {}),
                            "tunable": defaults.get("tunable", {}),
                            "strategy_finalized": defaults.get("strategy_finalized", False),
                        }
                    except Exception:
                        error_msg = html.Div([
                            html.Span("❌ Configuration snapshot missing. ", style={"color": "red", "fontWeight": "bold"}),
                            html.Span("Please select Strategy and Version to load parameters first."),
                        ])
                        return error_msg, run_name, {"bt_job_running": False}, "", None, ""
                else:
                    error_msg = html.Div([
                        html.Span("❌ Configuration snapshot missing. ", style={"color": "red", "fontWeight": "bold"}),
                        html.Span("Please select Strategy and Version to load parameters first."),
                    ])
                    return error_msg, run_name, {"bt_job_running": False}, "", None, ""

            version_to_use = bt_config_snapshot.get("version") or selected_version
            if not version_to_use:
                error_msg = html.Div("❌ Strategy version missing in snapshot", style={"color": "red"})
                return error_msg, run_name, {"bt_job_running": False}, "", None, ""
        
        # Legacy v2 path removed (inputs no longer exist)
        elif strategy in ["insidebar_intraday_v2"]:
            error_msg = html.Div("❌ Legacy InsideBar v2 path is not supported in UI", style={"color": "red"})
            return error_msg, run_name, {"bt_job_running": False}, "", None, ""
        
        # New Strategy: check if it's in registry but not migrated
        else:
            from src.strategies.config.registry import config_manager_registry
            if config_manager_registry.get_manager(strategy):
                error_msg = html.Div([
                    html.Span("⚠️ Strategy not migrated yet. ", style={"color": "orange", "fontWeight": "bold"}),
                    html.Span(f"Strategy '{strategy}' is registered but the runner interface is not yet updated for it."),
                ])
                return error_msg, run_name, {"bt_job_running": False}, "", None, ""

        # Validate inputs
        if not strategy or not symbols_str or not timeframe:
            return html.Div("❌ Please select strategy, symbols, and timeframe", style={"color": "red"}), run_name, {"bt_job_running": False}, "", None, ""

        # Validate symbols
        if not symbols_str or not symbols_str.strip():
            error_msg = html.Div([
                html.Span("⚠️ ", style={"color": "var(--accent-yellow)"}),
                html.Span("Error: Please enter at least one symbol"),
            ])
            return error_msg, run_name, {"bt_job_running": False}, "", None, ""

        symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]

        if not symbols:
            error_msg = html.Div([
                html.Span("⚠️ ", style={"color": "var(--accent-yellow)"}),
                html.Span("Error: Please enter at least one symbol"),
            ])
            return error_msg, run_name, {"bt_job_running": False}, "", None, ""

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
        config_params = {}
        if strategy == "insidebar_intraday":
            config_params = build_config_params(
                strategy, 
                version_to_use, 
                bt_config_snapshot, 
                compound_toggle_val, 
                equity_basis_val
            )

        logger.info(
            f"actions: backtest_params_from_ssot strategy_id={strategy} version={version_to_use} "
            f"total_params={len(config_params)} compound_enabled={'enabled' in (compound_toggle_val or [])}"
        )
        logger.info(f"🔍 [run_backtest] config_params payload: {config_params}")

        if strategy == "insidebar_intraday_v2":
            return html.Div("❌ Legacy InsideBar v2 path is not supported in UI", style={"color": "red"}), run_name, {"bt_job_running": False}, "", None, ""

        # session_filter is already in config_params from snapshot

        job_id = service.start_backtest(
            run_name=run_name,
            strategy=strategy,
            symbols=symbols,
            timeframe=timeframe,
            start_date=start_date_str,
            end_date=end_date_str,
            config_params=config_params if config_params else None,
        )
        trace_ui(
            step="ui_start_backtest",
            run_id=run_name,
            strategy_id=strategy,
            strategy_version=version_to_use,
            file=__file__,
            func="run_backtest",
            extra={"job_id": job_id},
        )

        # Format date range for display
        date_range_display = f"{start_date_str} to {end_date_str}" if start_date_str and end_date_str else "N/A"

        # SSOT: Store run_dir immediately for UI binding
        # Note: Adapter will return run_dir, but service wraps it
        # For now, derive run_dir from run_name (service doesn't pass back adapter response yet)
        from axiom_bt.pipeline.paths import get_backtest_run_dir
        active_run = {
            "job_id": job_id,
            "run_name": run_name,
            "run_dir": str(get_backtest_run_dir(run_name)),  # SSOT for all UI lookups
            "started_at": datetime.now().isoformat()
        }

        # Show progress indicator
        progress_msg = html.Div(
            [
                html.Div("🚀 Backtest started!", style={"color": "green", "fontWeight": "bold"}),
                html.Div(f"Run: {run_name}", style={"fontSize": "0.85em", "marginTop": "4px"}),
                html.Div(f"Job ID: {job_id}", style={"fontSize": "0.85em"}),
            ]
        )

        # Initial log message
        initial_log = html.Div([
            html.H6("📋 Pipeline Execution Log", style={"marginTop": "20px", "marginBottom": "10px"}),
            html.P("Backtest started... waiting for execution log...",
                   style={"color": "#888", "fontSize": "0.9em"})
        ])

        # Enable refresh interval to poll for completion via Store
        # Clear run name input for next run
        # Return active_run to store (SSOT)
        return progress_msg, "", {"bt_job_running": True}, initial_log, active_run, ""

    @app.callback(
        Output(RUN.PIPELINE_LOG, "children", allow_duplicate=True),
        Input(BT.REFRESH_BUTTON, "n_clicks"), # Using refresh button instead of interval if needed, but interval is also fine
        State(RUN.CURRENT_JOB_ID_STORE, "data"),  # This is actually active_run dict now
        prevent_initial_call=True
    )
    def update_pipeline_log(n_intervals, active_run):
        """Fetch and display pipeline execution log with progress bar."""
        from pathlib import Path
        from dash import no_update
        import json
        from ..config import BACKTESTS_DIR

        # No active job being tracked
        if not active_run:
            return no_update

        # SSOT: Use run_dir from active_run store (not job_id!)
        run_dir_str = active_run.get("run_dir") if isinstance(active_run, dict) else None

        if not run_dir_str:
            # Fallback for old format (just job_id string)
            # Try to get from service
            from ..services.backtest_service import get_backtest_service
            service = get_backtest_service()
            current_job_id = active_run if isinstance(active_run, str) else active_run.get("job_id")
            job_status = service.get_job_status(current_job_id)

            if not job_status or job_status.get("status") == "not_found":
                return no_update

            # Use run_name for directory
            actual_run_name = job_status.get("run_name", current_job_id)
            run_dir_str = f"{BACKTESTS_DIR}/{actual_run_name}"

        run_dir = Path(run_dir_str)

        # DEBUG MODE: Show directory resolution details
        import os
        debug_mode = os.getenv("DASH_BACKTEST_DEBUG") == "1"

        if debug_mode:
            # High-contrast debug panel styling
            debug_style = {
                "marginTop": "20px",
                "padding": "16px",
                "backgroundColor": "var(--bs-card-bg, #2b2b2b)",
                "border": "2px solid var(--bs-warning, #ffc107)",
                "borderRadius": "6px",
                "color": "var(--bs-body-color, #eaeaea)",
            }

            label_style = {
                "fontWeight": "600",
                "color": "var(--bs-warning, #ffc107)"
            }

            value_style = {
                "fontFamily": "monospace",
                "color": "var(--bs-body-color, #eaeaea)"
            }
            # Show debug panel with directory resolution details
            job_id = active_run.get("job_id") if isinstance(active_run, dict) else active_run
            run_name = active_run.get("run_name") if isinstance(active_run, dict) else "unknown"

            debug_info = [
                html.H6("🐛 Debug Mode", style={**label_style, "marginBottom": "10px"}),
                html.Div([
                    html.Span("Job ID: ", style=label_style),
                    html.Span(str(job_id), style=value_style), html.Br(),
                    html.Span("Run Name: ", style=label_style),
                    html.Span(run_name, style=value_style), html.Br(),
                    html.Span("Run Dir: ", style=label_style),
                    html.Span(str(run_dir), style=value_style), html.Br(),
                ], style={"fontSize": "0.85em", "marginBottom": "10px"}),
            ]

            # Check directory existence
            if run_dir.exists():
                files_in_dir = list(run_dir.glob("*"))
                debug_info.append(
                    html.Div([
                        html.Span("✅ Directory exists", style={"color": "#28a745", "fontWeight": "600"}),
                        html.Br(),
                        html.Small(f"Files: {', '.join([f.name for f in files_in_dir[:10]])}")
                    ], style={"marginTop": "8px", "color": "var(--bs-body-color, #eaeaea)"})
                )
            else:
                # Search for candidate directories
                backtests_path = Path(BACKTESTS_DIR)
                prefix = run_name[:15] if run_name else ""
                candidates = list(backtests_path.glob(f"{prefix}*")) if prefix else []

                debug_info.append(
                    html.Div([
                        html.Span("❌ Expected directory NOT FOUND",
                                 style={"color": "#dc3545", "fontWeight": "600"}),
                        html.Br(),
                        html.Small(f"Searched for prefix: {prefix}*"),
                        html.Br(),
                        html.Small(f"Candidates found: {len(candidates)}"),
                    ], style={"marginTop": "8px", "color": "var(--bs-body-color, #eaeaea)"})
                )

                if candidates:
                    debug_info.append(
                        html.Div([
                            html.Strong("Candidate dirs:", style=label_style),
                            html.Ul([html.Li(str(c.name), style=value_style) for c in candidates[:5]])
                        ], style={"marginTop": "8px", "fontSize": "0.8em"})
                    )

            return html.Div(debug_info, style=debug_style)

        # ===== NEW: Render pipeline steps from run_steps.jsonl =====
        steps_file = run_dir / "run_steps.jsonl"

        if steps_file.exists():
            try:
                # Read all step events
                step_events = []
                with open(steps_file) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            step_events.append(json.loads(line))

                if step_events:
                    # Group events by step_index for display
                    steps_by_index = {}
                    for event in step_events:
                        idx = event["step_index"]
                        if idx not in steps_by_index:
                            steps_by_index[idx] = []
                        steps_by_index[idx].append(event)

                    # Build step display elements
                    step_elements = []
                    for idx in sorted(steps_by_index.keys()):
                        events = steps_by_index[idx]
                        step_name = events[0]["step_name"]

                        # Determine final status
                        statuses = [e["status"] for e in events]
                        if "failed" in statuses:
                            final_status = "failed"
                            icon = "❌"
                            color = "#dc3545"
                        elif "skipped" in statuses:
                            final_status = "skipped"
                            icon = "⏭️"
                            color = "#6c757d"
                        elif "completed" in statuses:
                            final_status = "completed"
                            icon = "✅"
                            color = "#28a745"
                        elif "started" in statuses:
                            final_status = "running"
                            icon = "⏳"
                            color = "#ffc107"
                        else:
                            final_status = "unknown"
                            icon = "❔"
                            color = "#000"

                        step_elements.append(
                            html.Div([
                                html.Span(icon, style={"marginRight": "8px", "fontSize": "1.1em"}),
                                html.Span(
                                    step_name.replace("_", " ").title(),
                                    style={"fontWeight": "600" if final_status == "running" else "normal", "color": color}
                                ),
                            ], style={"padding": "6px 0", "display": "flex", "alignItems": "center"})
                        )

                    return html.Div([
                        html.H6("📋 Pipeline Steps", style={"marginTop": "20px", "marginBottom": "12px", "color": "var(--bs-body-color, #333)"}),
                        html.Div(step_elements, style={
                            "backgroundColor": "var(--bs-card-bg, #fff)",
                            "padding": "12px",
                            "borderRadius": "6px",
                            "border": "1px solid var(--bs-border-color, #dee2e6)"
                        })
                    ])
            except Exception as e:
                logger.error(f"Failed to render steps: {e}")
                # Fall through to run_result.json check

        # HOTFIX: Check for NEW pipeline artifacts (run_result.json)
        run_result_file = run_dir / "run_result.json"

        if run_result_file.exists():
            try:
                with open(run_result_file) as f:
                    result = json.load(f)

                status = result.get("status", "unknown")
                reason = result.get("reason")
                error_id = result.get("error_id")
                details = result.get("details", {})

                if status == "success":
                    return html.Div([
                        html.H6("📋 Pipeline Execution", style={"marginTop": "20px", "marginBottom": "15px"}),
                        html.Div("✅ Backtest completed successfully",
                                style={"color": "#28a745", "fontWeight": "600", "marginBottom": "12px"}),
                        html.Div(f"Signals: {details.get('signals_count', 'N/A')}",
                                style={"fontSize": "0.9em", "color": "#666"}),
                    ], style={"marginTop": "20px", "padding": "16px", "backgroundColor": "#fff",
                             "border": "1px solid #28a745", "borderRadius": "6px"})

                elif status == "failed_precondition":
                    return html.Div([
                        html.H6("📋 Pipeline Execution", style={"marginTop": "20px", "marginBottom": "15px"}),
                        html.Div(f"⚠️ Gates blocked: {reason}",
                                style={"color": "#ffc107", "fontWeight": "600", "marginBottom": "12px"}),
                    ], style={"marginTop": "20px", "padding": "16px", "backgroundColor": "#fff",
                             "border": "2px solid #ffc107", "borderRadius": "6px"})

                elif status == "error":
                    return html.Div([
                        html.H6("📋 Pipeline Execution", style={"marginTop": "20px", "marginBottom": "15px"}),
                        html.Div(f"❌ Error (ID: {error_id})",
                                style={"color": "#dc3545", "fontWeight": "600", "marginBottom": "12px"}),
                    ], style={"marginTop": "20px", "padding": "16px", "backgroundColor": "#fff",
                             "border": "2px solid #dc3545", "borderRadius": "6px"})

            except Exception:
                pass  # Fall through to old logic

        # FALLBACK: Old pipeline log format
        from ..utils.backtest_log_utils import (
            get_pipeline_log_state,
            format_step_icon,
            format_step_color,
        )

        log_state = get_pipeline_log_state(current_job_id, BACKTESTS_DIR)

        # Use utility to parse log
        log_state = get_pipeline_log_state(current_job_id, BACKTESTS_DIR)

        # No log file yet
        if log_state.total_steps == 0 and log_state.overall_status == "pending":
            return html.Div([
                html.H6("📋 Pipeline Execution Log", style={"marginTop": "20px", "marginBottom": "10px"}),
                dbc.Spinner(size="sm", color="primary", spinner_style={"marginRight": "8px"}),
                html.Span("⏳ Waiting for pipeline to start...",
                         style={"color": "#888", "fontSize": "0.9em"})
            ])

        # Error reading log
        if log_state.total_steps == 0 and log_state.overall_status == "error":
            return html.Div([
                html.H6("📋 Pipeline Execution Log", style={"marginTop": "20px", "marginBottom": "10px"}),
                html.P(f"❌ Error reading log for run: {current_job_id}",
                       style={"color": "#dc3545", "fontSize": "0.9em"})
            ])

        # Build display with progress bar
        display_components = []

        # Header with title
        display_components.append(
            html.H6("📋 Pipeline Execution",
                   style={"marginTop": "20px", "marginBottom": "15px", "fontWeight": "600"})
        )

        # Progress bar
        progress_color = "success" if log_state.overall_status == "success" else \
                        "danger" if log_state.overall_status == "error" else \
                        "info"

        progress_label = f"Step {log_state.completed_steps}/{log_state.total_steps}"
        if log_state.current_step:
            progress_label += f": {log_state.current_step}"

        display_components.append(
            html.Div([
                html.Div(progress_label,
                        style={"fontSize": "0.85em", "marginBottom": "6px", "fontWeight": "500"}),
                dbc.Progress(
                    value=log_state.progress_pct,
                    color=progress_color,
                    striped=log_state.overall_status == "running",
                    animated=log_state.overall_status == "running",
                    style={"height": "20px", "marginBottom": "16px"},
                    className="mb-3"
                )
            ])
        )

        # Overall status badge
        if log_state.overall_status == "success":
            display_components.append(
                html.Div("✅ Pipeline completed successfully",
                        style={"color": "#28a745", "fontWeight": "600", "marginBottom": "12px"})
            )
        elif log_state.overall_status == "error":
            display_components.append(
                html.Div("❌ Pipeline failed",
                        style={"color": "#dc3545", "fontWeight": "600", "marginBottom": "12px"})
            )
        elif log_state.overall_status == "running":
            display_components.append(
                html.Div([
                    dbc.Spinner(size="sm", color="primary", spinner_style={"marginRight": "6px"}),
                    html.Span("🔄 Pipeline running...", style={"fontWeight": "600"})
                ], style={"color": "#007bff", "marginBottom": "12px"})
            )

        # Compact step list
        steps_display = []
        for idx, step in enumerate(log_state.steps, 1):
            icon = format_step_icon(step.status)
            color = format_step_color(step.status)

            # Determine if this is the current step
            is_current = (step.name == log_state.current_step)

            step_style = {
                "padding": "8px 12px",
                "marginBottom": "4px",
                "borderLeft": f"3px solid {color}",
                "backgroundColor": "#f8f9fa" if not is_current else "#e3f2fd",
                "borderRadius": "3px",
                "fontSize": "0.9em",
            }

            step_content = [
                html.Span(f"{icon} ", style={"marginRight": "6px", "fontSize": "1.1em"}),
                html.Span(f"{idx}. ", style={"fontWeight": "600", "color": "#666", "marginRight": "4px"}),
                html.Span(step.name, style={"fontWeight": "500" if is_current else "normal"}),
            ]

            # Add duration if available
            if step.duration is not None:
                step_content.append(
                    html.Span(f" ({step.duration:.1f}s)",
                             style={"fontSize": "0.85em", "color": "#999", "marginLeft": "6px"})
                )

            # Add current indicator
            if is_current:
                step_content.append(
                    html.Span(" ← current",
                             style={"fontSize": "0.8em", "color": "#007bff",
                                   "marginLeft": "8px", "fontStyle": "italic"})
                )

            steps_display.append(html.Div(step_content, style=step_style))

        display_components.append(html.Div(steps_display, style={"marginTop": "12px"}))

        # Wrap everything
        return html.Div(
            display_components,
            style={
                "marginTop": "20px",
                "padding": "16px",
                "backgroundColor": "#fff",
                "border": "1px solid #dee2e6",
                "borderRadius": "6px",
            }
        )

    @app.callback(
        Output(RUN.PROGRESS_CONTAINER, "children", allow_duplicate=True),
        Output("nav:refresh-policy", "data", allow_duplicate=True),
        Output(BT.RUN_STATUS_ICON, "children"),  # NEW: Status icon
        Input(Nav.REFRESH_INTERVAL, "n_intervals"),
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
            # No jobs to display - clear progress and icon
            return "", {"bt_job_running": False}, ""

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
                                id=BT.ERROR_COLLAPSE_BTN(job_id),
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
                            id=BT.ERROR_COLLAPSE(job_id),
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

        # Determine status icon based on job states
        status_icon = ""
        if running_jobs:
            status_icon = html.Span(
                "⏳ Running...",
                style={"color": "#888", "fontSize": "0.9em"}
            )
        elif recent_jobs:
            # Check if any completed successfully
            completed_jobs = [j for j in recent_jobs.values() if j.get("status") == "completed"]
            failed_jobs = [j for j in recent_jobs.values() if j.get("status") == "failed"]

            if completed_jobs and not failed_jobs:
                status_icon = html.Span(
                    "✅ Complete - Click refresh to update results",
                    style={"color": "green", "fontSize": "0.9em"}
                )
            elif failed_jobs:
                status_icon = html.Span(
                    "⚠️ Failed - Click refresh to see details",
                    style={"color": "orange", "fontSize": "0.9em"}
                )

        return html.Div(job_statuses), {"bt_job_running": len(running_jobs) > 0}, status_icon

def build_config_params(strategy, version_to_use, bt_config_snapshot, compound_toggle_val, equity_basis_val):
    """Refactored logic to build config params for testability."""
    config_params = {}
    if strategy == "insidebar_intraday":
        # SSOT Path: Use Snapshot from Store
        core = bt_config_snapshot.get("core", {})
        tunable = bt_config_snapshot.get("tunable", {})
        
        # Merge all into runner config
        config_params = {**core, **tunable}
        config_params["strategy_version"] = version_to_use

        # --- Compound Settings (Opt-in) ---
        compound_enabled = "enabled" in (compound_toggle_val or [])
        if compound_enabled:
            config_params["backtesting"] = {
                "compound_sizing": True,
                "compound_equity_basis": equity_basis_val or "cash_only"
            }
    return config_params
