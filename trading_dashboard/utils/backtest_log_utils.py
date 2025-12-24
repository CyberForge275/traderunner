"""Backtest Pipeline Log Utilities - Parse and format pipeline execution logs.

This module provides utilities for parsing run_log.json files and calculating
progress metrics for the Pipeline Execution Log UI component.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LogStep:
    """Single pipeline step."""
    name: str
    status: str  # pending, running, success, warning, error
    duration: Optional[float] = None
    details: str = ""
    kind: str = ""  # command, message, step, etc.


@dataclass
class PipelineLogState:
    """Complete state of a pipeline execution log."""
    steps: List[LogStep]
    progress_pct: float
    current_step: Optional[str]
    overall_status: str  # running, success, error
    total_steps: int
    completed_steps: int


def get_pipeline_log_state(run_id: str, backtests_dir: Path) -> PipelineLogState:
    """Parse run_log.json and return structured pipeline state.

    Args:
        run_id: Name of the backtest run
        backtests_dir: Path to artifacts/backtests directory

    Returns:
        PipelineLogState with progress and step information
    """
    log_path = backtests_dir / run_id / "run_log.json"

    # Default empty state
    if not log_path.exists():
        return PipelineLogState(
            steps=[],
            progress_pct=0.0,
            current_step=None,
            overall_status="pending",
            total_steps=0,
            completed_steps=0
        )

    # Read and parse log
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            run_log = json.load(f)
    except (json.JSONDecodeError, OSError):
        return PipelineLogState(
            steps=[],
            progress_pct=0.0,
            current_step=None,
            overall_status="error",
            total_steps=0,
            completed_steps=0
        )

    # Extract entries and overall status
    entries = run_log.get('entries', [])
    overall_status = run_log.get('status', 'running')

    # Parse steps
    steps: List[LogStep] = []
    current_step: Optional[str] = None

    for entry in entries:
        kind = entry.get('kind', '')

        # Skip meta entries
        if kind in ['run_meta']:
            continue

        title = entry.get('title') or entry.get('phase') or f"Step {len(steps) + 1}"
        status = entry.get('status', 'running')
        duration = entry.get('duration')
        details = entry.get('message') or entry.get('details') or entry.get('command') or ''

        step = LogStep(
            name=title,
            status=status,
            duration=duration,
            details=str(details) if details else '',
            kind=kind
        )
        steps.append(step)

        # Track current step (last non-completed step or last step overall)
        if status == 'running':
            current_step = title

    # If no running step but pipeline is running, use last step
    if not current_step and steps and overall_status == 'running':
        current_step = steps[-1].name

    # Calculate progress
    total_steps = len(steps)
    completed_steps = sum(1 for s in steps if s.status in ['success', 'warning', 'error'])

    if total_steps > 0:
        progress_pct = (completed_steps / total_steps) * 100
    else:
        progress_pct = 0.0

    return PipelineLogState(
        steps=steps,
        progress_pct=progress_pct,
        current_step=current_step,
        overall_status=overall_status,
        total_steps=total_steps,
        completed_steps=completed_steps
    )


def format_step_icon(status: str) -> str:
    """Get icon for step status."""
    icons = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'running': '⏳',
        'pending': '○',
    }
    return icons.get(status, '•')


def format_step_color(status: str) -> str:
    """Get color code for step status."""
    colors = {
        'success': '#28a745',
        'error': '#dc3545',
        'warning': '#ffc107',
        'running': '#007bff',
        'pending': '#6c757d',
    }
    return colors.get(status, '#6c757d')
