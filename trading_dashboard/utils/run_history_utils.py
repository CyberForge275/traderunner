"""
Run History Utilities for Pre-PaperTrading Lab
================================================

Helper functions to fetch and format strategy run history for UI display.
"""

import json
from typing import List, Dict, Optional
from datetime import datetime

from trading_dashboard.repositories.strategy_metadata import (
    get_repository,
    LabStage,
)
from trading_dashboard.utils.version_resolver import resolve_pre_paper_version


def get_pre_paper_run_history(
    strategy_key: str,
    limit: int = 10
) -> List[Dict]:
    """
    Get run history for a strategy in Pre-PaperTrading Lab.

    Fetches the last N runs for the currently valid Pre-Paper version
    of the specified strategy.

    Args:
        strategy_key: Strategy identifier (e.g., "insidebar_intraday")
        limit: Maximum number of runs to return (default: 10)

    Returns:
        List of run dictionaries with UI-friendly formatting.
        Empty list if no version or no runs exist.

    Example:
        [
            {
                "run_id": 4,
                "started_at": "2025-12-15 12:07:14",
                "ended_at": "2025-12-15 12:07:14",
                "run_type": "replay",
                "status": "completed",
                "signals": 0,
                "symbols": "AAPL",
                "duration_seconds": 0.4
            },
            ...
        ]
    """
    repo = get_repository()

    try:
        # Resolve current Pre-Paper version
        version = resolve_pre_paper_version(strategy_key)
    except ValueError:
        # No valid version exists - return empty history
        return []

    # Fetch runs for this version (Pre-Paper only)
    runs = repo.get_runs_for_strategy_version(
        version_id=version.id,
        lab_stage=LabStage.PRE_PAPERTRADE
    )

    # Limit results
    runs = runs[:limit]

    # Format for UI
    formatted_runs = []
    for run in runs:
        formatted_run = {
            "run_id": run.id,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "run_type": run.run_type,
            "status": run.status,
            "environment": run.environment,
        }

        # Extract metrics from metrics_json
        if run.metrics_json:
            try:
                metrics = json.loads(run.metrics_json)
                formatted_run["signals"] = metrics.get("number_of_signals", 0)
                formatted_run["symbols_requested"] = metrics.get("symbols_requested_count", 0)
            except json.JSONDecodeError:
                formatted_run["signals"] = None
                formatted_run["symbols_requested"] = None
        else:
            formatted_run["signals"] = None
            formatted_run["symbols_requested"] = None

        # Extract symbols from tags
        if run.tags:
            try:
                tags = json.loads(run.tags)
                symbols = tags.get("symbols", [])
                if isinstance(symbols, list):
                    formatted_run["symbols"] = ", ".join(symbols) if symbols else "N/A"
                else:
                    formatted_run["symbols"] = str(symbols)
            except json.JSONDecodeError:
                formatted_run["symbols"] = "N/A"
        else:
            formatted_run["symbols"] = "N/A"

        # Calculate duration if both timestamps available
        if run.started_at and run.ended_at:
            try:
                # Parse timestamps (handle various formats)
                if isinstance(run.started_at, str):
                    start = datetime.fromisoformat(run.started_at.replace('Z', '+00:00'))
                else:
                    start = run.started_at

                if isinstance(run.ended_at, str):
                    end = datetime.fromisoformat(run.ended_at.replace('Z', '+00:00'))
                else:
                    end = run.ended_at

                duration = (end - start).total_seconds()
                formatted_run["duration_seconds"] = round(duration, 2)
            except (ValueError, AttributeError):
                formatted_run["duration_seconds"] = None
        else:
            formatted_run["duration_seconds"] = None

        formatted_runs.append(formatted_run)

    return formatted_runs


def format_run_history_for_table(runs: List[Dict]) -> List[Dict]:
    """
    Format run history for Dash DataTable display.

    Converts run dictionaries to table-friendly format with
    human-readable strings.

    Args:
        runs: List of run dictionaries from get_pre_paper_run_history()

    Returns:
        List of dictionaries suitable for dash_table.DataTable
    """
    table_data = []

    for run in runs:
        # Format datetime to readable string
        if run.get("started_at"):
            try:
                if isinstance(run["started_at"], str):
                    dt = datetime.fromisoformat(run["started_at"].replace('Z', '+00:00'))
                else:
                    dt = run["started_at"]
                date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, AttributeError):
                date_str = str(run["started_at"])
        else:
            date_str = "N/A"

        # Status badge formatting
        status_raw = run.get("status", "N/A")
        if status_raw == "completed":
            status_display = "✅ Completed"
        elif status_raw == "failed":
            status_display = "❌ Failed"
        elif status_raw == "running":
            status_display = "🔄 Running"
        else:
            status_display = status_raw.capitalize() if status_raw != "N/A" else "N/A"

        table_row = {
            "Run ID": run["run_id"],
            "Date/Time": date_str,
            "Mode": run["run_type"].capitalize() if run.get("run_type") else "N/A",
            "Status": status_display,  # With emoji badge
            "Signals": run.get("signals", "N/A"),
            "Symbols": run.get("symbols", "N/A"),
            "Duration": f"{run['duration_seconds']}s" if run.get("duration_seconds") is not None else "N/A"
        }

        table_data.append(table_row)

    return table_data
