"""Helpers for parsing run_steps.jsonl and run_result.json in UI callbacks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_run_steps(steps_file: Path) -> List[Dict[str, Any]]:
    """Parse step events and return per-step display payload."""
    if not steps_file.exists():
        return []

    step_events: List[Dict[str, Any]] = []
    with open(steps_file) as f:
        for line in f:
            line = line.strip()
            if line:
                step_events.append(json.loads(line))

    if not step_events:
        return []

    steps_by_index: Dict[int, List[Dict[str, Any]]] = {}
    for event in step_events:
        idx = event["step_index"]
        if idx not in steps_by_index:
            steps_by_index[idx] = []
        steps_by_index[idx].append(event)

    parsed: List[Dict[str, Any]] = []
    for idx in sorted(steps_by_index.keys()):
        events = steps_by_index[idx]
        step_name = events[0]["step_name"]
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
        parsed.append(
            {
                "step_index": idx,
                "step_name": step_name,
                "final_status": final_status,
                "icon": icon,
                "color": color,
            }
        )
    return parsed


def parse_run_result(run_result_file: Path) -> Optional[Dict[str, Any]]:
    """Parse run_result.json and return normalized payload for UI rendering."""
    if not run_result_file.exists():
        return None
    with open(run_result_file) as f:
        result = json.load(f)
    return {
        "status": result.get("status", "unknown"),
        "reason": result.get("reason"),
        "error_id": result.get("error_id"),
        "details": result.get("details", {}) or {},
    }

