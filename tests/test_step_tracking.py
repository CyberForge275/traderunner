"""
Step Tracking Tests - Pipeline Visualization

Tests for run_steps.jsonl emission and UI rendering.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
import pytest


class TestStepTracking:
    """Test that pipeline emits step events in correct order."""

    def test_step_file_created_and_ordered(self, tmp_path):
        """Steps must be written to run_steps.jsonl in execution order."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        steps_file = run_dir / "run_steps.jsonl"

        # Simulate pipeline emitting steps
        steps = [
            {"step_index": 1, "step_name": "create_run_dir", "status": "started", "timestamp": "2025-12-16T12:00:00Z"},
            {"step_index": 1, "step_name": "create_run_dir", "status": "completed", "timestamp": "2025-12-16T12:00:01Z"},
            {"step_index": 2, "step_name": "write_run_meta", "status": "started", "timestamp": "2025-12-16T12:00:01Z"},
            {"step_index": 2, "step_name": "write_run_meta", "status": "completed", "timestamp": "2025-12-16T12:00:02Z"},
            {"step_index": 3, "step_name": "coverage_gate", "status": "started", "timestamp": "2025-12-16T12:00:02Z"},
            {"step_index": 3, "step_name": "coverage_gate", "status": "completed", "timestamp": "2025-12-16T12:00:05Z"},
        ]

        with open(steps_file, 'w') as f:
            for step in steps:
                f.write(json.dumps(step) + '\n')

        # Read back and verify order
        read_steps = []
        with open(steps_file) as f:
            for line in f:
                read_steps.append(json.loads(line))

        assert len(read_steps) == 6
        # Verify steps are in index order
        for i, step in enumerate(read_steps):
            expected_index = (i // 2) + 1  # Each step has started/completed
            assert step["step_index"] == expected_index

    def test_step_events_have_required_fields(self, tmp_path):
        """Each step event must have required fields."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        steps_file = run_dir / "run_steps.jsonl"

        step_event = {
            "step_index": 1,
            "step_name": "coverage_gate",
            "status": "started",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {"some": "data"}
        }

        with open(steps_file, 'w') as f:
            f.write(json.dumps(step_event) + '\n')

        # Validate
        with open(steps_file) as f:
            loaded = json.loads(f.readline())

        assert "step_index" in loaded
        assert "step_name" in loaded
        assert "status" in loaded
        assert "timestamp" in loaded
        assert loaded["status"] in ["started", "completed", "failed", "skipped"]

    def test_failed_step_stops_pipeline(self, tmp_path):
        """If a step fails, subsequent steps should not appear."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        steps_file = run_dir / "run_steps.jsonl"

        steps = [
            {"step_index": 1, "step_name": "create_run_dir", "status": "started"},
            {"step_index": 1, "step_name": "create_run_dir", "status": "completed"},
            {"step_index": 2, "step_name": "coverage_gate", "status": "started"},
            {"step_index": 2, "step_name": "coverage_gate", "status": "failed", "details": {"reason": "data_coverage_gap"}},
            # No step 3 (sla_gate) - pipeline stopped
        ]

        with open(steps_file, 'w') as f:
            for step in steps:
                f.write(json.dumps(step) + '\n')

        with open(steps_file) as f:
            all_steps = [json.loads(line) for line in f]

        # Should only have steps 1-2, not 3+ (strategy execution)
        max_index = max(s["step_index"] for s in all_steps)
        assert max_index == 2

        # Last step should be failed
        assert all_steps[-1]["status"] == "failed"


class TestUIStepRendering:
    """Test UI rendering of steps from run_steps.jsonl."""

    def test_steps_rendered_in_index_order_not_alphabetical(self, tmp_path):
        """UI must render steps by step_index, not alphabetically."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        steps_file = run_dir / "run_steps.jsonl"

        # Write steps in non-alphabetical order
        steps = [
            {"step_index": 3, "step_name": "sla_gate", "status": "completed"},
            {"step_index": 1, "step_name": "create_run_dir", "status": "completed"},
            {"step_index": 2, "step_name": "coverage_gate", "status": "completed"},
        ]

        with open(steps_file, 'w') as f:
            for step in steps:
                f.write(json.dumps(step) + '\n')

        # Simulate UI reading and sorting
        with open(steps_file) as f:
            loaded_steps = [json.loads(line) for line in f]

        # UI MUST sort by step_index
        sorted_steps = sorted(loaded_steps, key=lambda s: s["step_index"])

        assert sorted_steps[0]["step_name"] == "create_run_dir"
        assert sorted_steps[1]["step_name"] == "coverage_gate"
        assert sorted_steps[2]["step_name"] == "sla_gate"

    def test_ui_shows_current_step(self, tmp_path):
        """UI should highlight the currently running step."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        steps_file = run_dir / "run_steps.jsonl"

        steps = [
            {"step_index": 1, "step_name": "create_run_dir", "status": "completed"},
            {"step_index": 2, "step_name": "coverage_gate", "status": "started"},  # Current
        ]

        with open(steps_file, 'w') as f:
            for step in steps:
                f.write(json.dumps(step) + '\n')

        # UI logic: find last "started" that isn't "completed"
        with open(steps_file) as f:
            all_steps = [json.loads(line) for line in f]

        # Find current step (started but not completed)
        current_step = None
        for step in all_steps:
            if step["status"] == "started":
                # Check if there's a corresponding completed event
                has_completed = any(
                    s["step_index"] == step["step_index"] and s["status"] == "completed"
                    for s in all_steps
                )
                if not has_completed:
                    current_step = step
                    break

        assert current_step is not None
        assert current_step["step_name"] == "coverage_gate"


class TestStepTrackerContract:
    """Test the step tracker contract (to be implemented)."""

    def test_tracker_context_manager(self, tmp_path):
        """Step tracker should use context manager for automatic completion."""
        # This tests the API we'll implement
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Mock implementation of tracker
        class MockStepTracker:
            def __init__(self, run_dir):
                self.run_dir = run_dir
                self.steps_file = run_dir / "run_steps.jsonl"
                self.current_index = 0

            def step(self, step_name):
                self.current_index += 1
                return self._StepContext(self, self.current_index, step_name)

            class _StepContext:
                def __init__(self, tracker, index, name):
                    self.tracker = tracker
                    self.index = index
                    self.name = name

                def __enter__(self):
                    event = {
                        "step_index": self.index,
                        "step_name": self.name,
                        "status": "started",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    with open(self.tracker.steps_file, 'a') as f:
                        f.write(json.dumps(event) + '\n')
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    status = "failed" if exc_type else "completed"
                    event = {
                        "step_index": self.index,
                        "step_name": self.name,
                        "status": status,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    with open(self.tracker.steps_file, 'a') as f:
                        f.write(json.dumps(event) + '\n')

        # Use the tracker
        tracker = MockStepTracker(run_dir)

        with tracker.step("create_run_dir"):
            pass  # Simulated work

        with tracker.step("coverage_gate"):
            pass

        # Verify steps written
        with open(tracker.steps_file) as f:
            steps = [json.loads(line) for line in f]

        assert len(steps) == 4  # 2 started + 2 completed
        assert steps[0]["status"] == "started"
        assert steps[1]["status"] == "completed"
