"""Job status helpers for backtest UI polling callbacks."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Tuple


TERMINAL_JOB_STATUSES = {"completed", "failed", "error", "failed_precondition"}


def collect_jobs_for_polling(
    all_jobs: Dict[str, Dict],
    current_time: float,
    window_seconds: int = 30,
) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
    """Select running jobs and recently finished terminal jobs for UI polling."""
    running_jobs = {jid: j for jid, j in all_jobs.items() if j.get("status") == "running"}
    recent_jobs: Dict[str, Dict] = {}
    for jid, job in all_jobs.items():
        if job.get("status") not in TERMINAL_JOB_STATUSES:
            continue
        ended_at = job.get("ended_at")
        if not ended_at:
            continue
        try:
            end_time = datetime.fromisoformat(ended_at).timestamp()
        except Exception:
            continue
        if current_time - end_time < window_seconds:
            recent_jobs[jid] = job
    return running_jobs, recent_jobs


def status_text(status: str) -> str:
    """User-facing label for a job status."""
    mapping = {
        "completed": "Completed Successfully",
        "failed": "Failed",
        "error": "Error",
        "failed_precondition": "Failed Precondition (Gates Blocked)",
    }
    return mapping.get(status, status.replace("_", " ").title() if status else "Unknown")


def status_icon_payload(running_jobs: Dict[str, Dict], recent_jobs: Dict[str, Dict]):
    """Return icon payload for UI status indicator."""
    if running_jobs:
        return {"text": "⏳ Running...", "color": "#888"}
    if not recent_jobs:
        return None
    completed_jobs = [j for j in recent_jobs.values() if j.get("status") == "completed"]
    failed_jobs = [j for j in recent_jobs.values() if j.get("status") != "completed"]
    if completed_jobs and not failed_jobs:
        return {"text": "✅ Complete - Click refresh to update results", "color": "green"}
    if failed_jobs:
        return {"text": "⚠️ Failed - Click refresh to see details", "color": "orange"}
    return None

