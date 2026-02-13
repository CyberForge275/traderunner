"""
Tests for BacktestDetailsService - SSOT reader for run details.

Service must read from run_manifest.json (preferred) or run_meta.json/run_result.json (fallback)
and run_steps.jsonl, never requiring run_log.json.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone
from trading_dashboard.services.backtest_details_service import (
    BacktestDetailsService,
    RunDetails,
    RunStep
)


class TestBacktestDetailsService:
    """Test manifest-based details loading (no run_log.json dependency)."""

    def test_load_summary_from_manifest(self, tmp_path):
        """
        RED TEST: Load run summary from run_manifest.json (preferred source).
        """
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Write run_manifest.json (production structure)
        manifest = {
            "identity": {
                "run_id": "test_run",
                "timestamp_utc": "2025-12-17T00:00:00+00:00",
                "commit_hash": "abc123",
                "market_tz": "America/New_York"
            },
            "strategy": {
                "key": "inside_bar",
                "impl_version": "1.0.0"
            },
            "data": {
                "symbol": "HOOD",
                "requested_tf": "M5"
            },
            "result": {
                "run_status": "success",
                "failure_reason": None
            }
        }
        with open(run_dir / "run_manifest.json", "w") as f:
            json.dump(manifest, f)

        service = BacktestDetailsService(artifacts_root=tmp_path)
        details = service.load_summary("test_run")

        assert details.run_id == "test_run"
        assert details.status == "SUCCESS"
        assert details.strategy_key == "inside_bar"
        assert details.symbols == ["HOOD"]
        assert details.requested_tf == "M5"
        assert details.source == "manifest"

    def test_load_summary_from_meta_fallback(self, tmp_path):
        """
        RED TEST: If no manifest, fall back to run_meta.json + run_result.json.
        """
        run_dir = tmp_path / "meta_only_run"
        run_dir.mkdir()

        # Write run_meta.json
        meta = {
            "run_id": "meta_only_run",
            "started_at": "2025-12-17T00:00:00+00:00",
            "strategy": {"key": "inside_bar"},
            "data": {
                "symbols": ["AAPL"],
                "timeframe": "M15"
            }
        }
        with open(run_dir / "run_meta.json", "w") as f:
            json.dump(meta, f)

        # Write run_result.json
        result = {
            "run_id": "meta_only_run",
            "finished_at": "2025-12-17T00:10:00+00:00",
            "status": "failed_precondition",
            "reason": "coverage_gap"
        }
        with open(run_dir / "run_result.json", "w") as f:
            json.dump(result, f)

        service = BacktestDetailsService(artifacts_root=tmp_path)
        details = service.load_summary("meta_only_run")

        assert details.run_id == "meta_only_run"
        assert details.status == "FAILED_PRECONDITION"
        assert details.strategy_key == "inside_bar"
        assert details.symbols == ["AAPL"]
        assert details.requested_tf == "M15"
        assert details.failure_reason == "coverage_gap"
        assert details.source == "meta+result"

    def test_manifest_without_run_status_falls_back_to_run_result_status(self, tmp_path):
        run_dir = tmp_path / "manifest_with_result_fallback"
        run_dir.mkdir()

        manifest = {
            "run_id": "manifest_with_result_fallback",
            "params": {"strategy_id": "insidebar_intraday"},
            "hashes": {},
        }
        with open(run_dir / "run_manifest.json", "w") as f:
            json.dump(manifest, f)

        with open(run_dir / "run_result.json", "w") as f:
            json.dump({"run_id": "manifest_with_result_fallback", "status": "success"}, f)

        service = BacktestDetailsService(artifacts_root=tmp_path)
        details = service.load_summary("manifest_with_result_fallback")

        assert details.source == "manifest"
        assert details.status == "SUCCESS"

    def test_load_steps_from_run_steps_jsonl(self, tmp_path):
        """
        RED TEST: Load steps from run_steps.jsonl, sorted by step_index.
        """
        run_dir = tmp_path / "steps_run"
        run_dir.mkdir()

        # Write run_steps.jsonl (out of order)
        steps = [
            {"step_index": 3, "step_name": "strategy_execute", "status": "completed", "timestamp": "2025-12-17T00:03:00+00:00"},
            {"step_index": 1, "step_name": "create_run_dir", "status": "completed", "timestamp": "2025-12-17T00:01:00+00:00"},
            {"step_index": 2, "step_name": "coverage_gate", "status": "completed", "timestamp": "2025-12-17T00:02:00+00:00"},
        ]
        with open(run_dir / "run_steps.jsonl", "w") as f:
            for step in steps:
                f.write(json.dumps(step) + "\n")

        service = BacktestDetailsService(artifacts_root=tmp_path)
        loaded_steps = service.load_steps("steps_run")

        # Must be sorted by step_index
        assert len(loaded_steps) == 3
        assert loaded_steps[0].step_name == "create_run_dir"
        assert loaded_steps[1].step_name == "coverage_gate"
        assert loaded_steps[2].step_name == "strategy_execute"
        assert all(s.status == "completed" for s in loaded_steps)

    def test_corrupt_manifest_returns_error_structure(self, tmp_path):
        """
        RED TEST: Corrupt JSON should return error details (not raise exception).
        """
        run_dir = tmp_path / "corrupt_run"
        run_dir.mkdir()

        # Write invalid JSON
        with open(run_dir / "run_manifest.json", "w") as f:
            f.write("{invalid json}")

        service = BacktestDetailsService(artifacts_root=tmp_path)
        details = service.load_summary("corrupt_run")

        assert details.status == "CORRUPT"
        assert details.error_message is not None
        assert "json" in details.error_message.lower() or "parse" in details.error_message.lower()
        assert details.source == "error"

    def test_missing_files_returns_incomplete_structure(self, tmp_path):
        """
        RED TEST: No artifacts at all should return INCOMPLETE status.
        """
        run_dir = tmp_path / "missing_run"
        run_dir.mkdir()
        # No files written

        service = BacktestDetailsService(artifacts_root=tmp_path)
        details = service.load_summary("missing_run")

        assert details.status == "INCOMPLETE"
        assert details.error_message is not None
        assert "no artifacts" in details.error_message.lower()

    def test_steps_with_durations(self, tmp_path):
        """
        TEST: If steps have timestamps, compute durations.
        """
        run_dir = tmp_path / "duration_run"
        run_dir.mkdir()

        # Steps with start/complete events
        events = [
            {"step_index": 1, "step_name": "step_a", "status": "started", "timestamp": "2025-12-17T00:00:00+00:00"},
            {"step_index": 1, "step_name": "step_a", "status": "completed", "timestamp": "2025-12-17T00:00:05+00:00"},
            {"step_index": 2, "step_name": "step_b", "status": "started", "timestamp": "2025-12-17T00:00:05+00:00"},
            {"step_index": 2, "step_name": "step_b", "status": "completed", "timestamp": "2025-12-17T00:00:10+00:00"},
        ]
        with open(run_dir / "run_steps.jsonl", "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        service = BacktestDetailsService(artifacts_root=tmp_path)
        steps = service.load_steps("duration_run")

        assert len(steps) == 2
        assert steps[0].step_name == "step_a"
        assert steps[0].duration_seconds == 5.0
        assert steps[1].step_name == "step_b"
        assert steps[1].duration_seconds == 5.0
