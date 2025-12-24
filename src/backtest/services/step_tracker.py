"""
Pipeline Step Tracker - Emit step events to run_steps.jsonl

Provides visibility into pipeline execution for UI rendering.
Each major step emits start/complete/fail events with timestamps.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextlib import contextmanager


class StepTracker:
    """
    Tracks pipeline execution steps and emits events to run_steps.jsonl.

    Usage:
        tracker = StepTracker(run_dir)

        with tracker.step("coverage_gate"):
            # Do coverage check work
            pass

        # Auto-emits: {"step_index": 1, "step_name": "coverage_gate", "status": "started", ...}
        # Then: {"step_index": 1, "step_name": "coverage_gate", "status": "completed", ...}
    """

    def __init__(self, run_dir: Path):
        """
        Initialize step tracker.

        Args:
            run_dir: Directory where run_steps.jsonl will be written
        """
        self.run_dir = Path(run_dir)
        self.steps_file = self.run_dir / "run_steps.jsonl"
        self.current_index = 0

    @contextmanager
    def step(self, step_name: str, details: Optional[Dict[str, Any]] = None):
        """
        Track a pipeline step with automatic start/complete emission.

        Args:
            step_name: Name of the step (e.g., "coverage_gate", "sla_gate")
            details: Optional additional details to include in event

        Yields:
            StepContext that can be used to add details during execution
        """
        self.current_index += 1
        step_index = self.current_index

        # Emit started event
        self._emit_event(
            step_index=step_index,
            step_name=step_name,
            status="started",
            details=details
        )

        context = _StepContext(step_index, step_name)

        try:
            yield context
            # Emit completed event
            self._emit_event(
                step_index=step_index,
                step_name=step_name,
                status="completed",
                details=context.details
            )
        except Exception as e:
            # Emit failed event
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
            if context.details:
                error_details.update(context.details)

            self._emit_event(
                step_index=step_index,
                step_name=step_name,
                status="failed",
                details=error_details
            )
            raise

    def skip_step(self, step_name: str, reason: str):
        """
        Mark a step as skipped (e.g., strategy execution skipped due to gate failure).

        Args:
            step_name: Name of the skipped step
            reason: Why it was skipped
        """
        self.current_index += 1
        self._emit_event(
            step_index=self.current_index,
            step_name=step_name,
            status="skipped",
            details={"reason": reason}
        )

    def _emit_event(
        self,
        step_index: int,
        step_name: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Emit a step event to run_steps.jsonl.

        Args:
            step_index: Sequential index of the step
            step_name: Name of the step
            status: "started" | "completed" | "failed" | "skipped"
            details: Optional additional details
        """
        event = {
            "step_index": step_index,
            "step_name": step_name,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if details:
            event["details"] = details

        # Append to jsonl file
        with open(self.steps_file, 'a') as f:
            f.write(json.dumps(event) + '\n')


class _StepContext:
    """Context object yielded by step() for adding details during execution."""

    def __init__(self, step_index: int, step_name: str):
        self.step_index = step_index
        self.step_name = step_name
        self.details: Dict[str, Any] = {}

    def add_detail(self, key: str, value: Any):
        """Add a detail to be included in the completion event."""
        self.details[key] = value


def read_steps(run_dir: Path) -> list[Dict[str, Any]]:
    """
    Read all step events from run_steps.jsonl.

    Args:
        run_dir: Directory containing run_steps.jsonl

    Returns:
        List of step event dictionaries
    """
    steps_file = run_dir / "run_steps.jsonl"

    if not steps_file.exists():
        return []

    steps = []
    with open(steps_file) as f:
        for line in f:
            line = line.strip()
            if line:
                steps.append(json.loads(line))

    return steps


def get_current_step(run_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Get the currently executing step (started but not completed/failed).

    Args:
        run_dir: Directory containing run_steps.jsonl

    Returns:
        Current step event dict, or None if no step is running
    """
    steps = read_steps(run_dir)

    # Find steps that are started but not completed/failed
    started_steps = {}
    for step in steps:
        key = (step["step_index"], step["step_name"])

        if step["status"] == "started":
            started_steps[key] = step
        elif step["status"] in ["completed", "failed", "skipped"]:
            started_steps.pop(key, None)

    # Return the earliest started step (if any)
    if started_steps:
        return min(started_steps.values(), key=lambda s: s["step_index"])

    return None
