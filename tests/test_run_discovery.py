"""
Tests for RunDiscoveryService - Manifest-based run discovery.

Tests-first approach to fix critical bug: runs with run_meta.json/run_manifest.json
are invisible in UI dropdown because current code only looks for run_log.json.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone
from trading_dashboard.services.run_discovery_service import (
    RunDiscoveryService,
    BacktestRunSummary
)


class TestRunDiscovery:
    """Test manifest-based run discovery (no directory name parsing)."""
    
    def test_includes_nonstandard_dir_name_via_run_meta(self, tmp_path):
        """
        RED TEST: Run with non-standard directory name MUST be discovered
        via run_meta.json, never by parsing directory name.
        
        This tests the actual bug: 251216_234616_HOOD4_2d is invisible.
        """
        # Create run with non-standard directory name
        run_dir = tmp_path / "251216_234616_HOOD4_2d"
        run_dir.mkdir()
        
        # Write run_meta.json with correct metadata
        run_meta = {
            "run_id": "251216_234616_HOOD4_2d",
            "started_at": "2025-12-16T22:46:16.937921+00:00",
            "strategy": {"key": "inside_bar"},
            "data": {
                "symbols": ["HOOD"],
                "timeframe": "M5",
                "requested_end": "2025-12-15",
                "lookback_days": 2
            }
        }
        with open(run_dir / "run_meta.json", "w") as f:
            json.dump(run_meta, f)
        
        # Discover runs
        service = RunDiscoveryService(artifacts_root=tmp_path)
        runs = service.discover()
        
        # MUST find the run
        assert len(runs) == 1
        run = runs[0]
        
        # MUST extract symbol/tf from metadata, NOT directory name
        assert run.run_id == "251216_234616_HOOD4_2d"
        assert run.symbols == ["HOOD"]
        assert run.requested_tf == "M5"
        assert run.strategy_key == "inside_bar"
        assert run.status != "CORRUPT"
    
    def test_corrupt_json_marked_as_corrupt_not_dropped(self, tmp_path):
        """
        RED TEST: If run_meta.json exists but is corrupt, run MUST still
        be listed with status="CORRUPT" and parse_error set.
        
        Never silently drop runs.
        """
        run_dir = tmp_path / "corrupt_run_test"
        run_dir.mkdir()
        
        # Write invalid JSON
        with open(run_dir / "run_meta.json", "w") as f:
            f.write("{invalid json here")
        
        service = RunDiscoveryService(artifacts_root=tmp_path)
        runs = service.discover()
        
        # MUST include the corrupt run
        assert len(runs) == 1
        run = runs[0]
        
        assert run.status == "CORRUPT"
        assert run.parse_error is not None
        assert "json" in run.parse_error.lower() or "parse" in run.parse_error.lower()
        assert run.run_id == "corrupt_run_test"
    
    def test_prefers_manifest_over_meta_when_both_exist(self, tmp_path):
        """
        RED TEST: When both run_manifest.json and run_meta.json exist,
        discovery MUST prefer run_manifest.json (more complete).
        """
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        
        # Write run_meta.json
        run_meta = {
            "run_id": "test_run",
            "started_at": "2025-12-16T10:00:00+00:00",
            "strategy": {"key": "inside_bar"},
            "data": {"symbols": ["AAPL"], "timeframe": "M5"}
        }
        with open(run_dir / "run_meta.json", "w") as f:
            json.dump(run_meta, f)
        
        # Write run_manifest.json with DIFFERENT data (actual manifest structure)
        run_manifest = {
            "identity": {
                "run_id": "test_run",
                "timestamp_utc": "2025-12-16T11:00:00+00:00"  # Different!
            },
            "strategy": {
                "key": "inside_bar_v2"  # Different!
            },
            "data": {
                "symbol": "MSFT",  # Different! (singular)
                "requested_tf": "M15"  # Different!
            },
            "result": {
                "run_status": "success"
            }
        }
        with open(run_dir / "run_manifest.json", "w") as f:
            json.dump(run_manifest, f)
        
        service = RunDiscoveryService(artifacts_root=tmp_path)
        runs = service.discover()
        
        assert len(runs) == 1
        run = runs[0]
        
        # MUST use manifest data (not meta data)
        assert run.strategy_key == "inside_bar_v2"
        assert run.symbols == ["MSFT"]
        assert run.requested_tf == "M15"
        assert run.started_at.hour == 11  # From manifest, not meta
    
    def test_reads_steps_from_run_steps_jsonl(self, tmp_path):
        """
        RED TEST: If run_steps.jsonl exists, discovery MUST load steps
        and provide step count, sorted by step_index.
        """
        run_dir = tmp_path / "test_run_with_steps"
        run_dir.mkdir()
        
        # Write run_meta.json
        run_meta = {
            "run_id": "test_run_with_steps",
            "started_at": "2025-12-16T10:00:00+00:00",
            "strategy": {"key": "inside_bar"},
            "data": {"symbols": ["TEST"], "timeframe": "M5"}
        }
        with open(run_dir / "run_meta.json", "w") as f:
            json.dump(run_meta, f)
        
        # Write run_steps.jsonl with steps in random order
        steps = [
            {"step_index": 3, "step_name": "strategy_execute", "status": "completed"},
            {"step_index": 1, "step_name": "create_run_dir", "status": "completed"},
            {"step_index": 2, "step_name": "coverage_gate", "status": "completed"},
        ]
        with open(run_dir / "run_steps.jsonl", "w") as f:
            for step in steps:
                f.write(json.dumps(step) + "\n")
        
        service = RunDiscoveryService(artifacts_root=tmp_path)
        runs = service.discover()
        
        assert len(runs) == 1
        run = runs[0]
        
        assert run.has_steps is True
        assert run.steps_count == 3
        
        # Steps should be available (implementation will add steps property)
        # For now, just verify count
    
    def test_dropdown_refresh_lists_new_run_after_creation(self, tmp_path):
        """
        RED TEST: After creating a new run, calling discover() again
        MUST include the new run. (Pure function test, no caching)
        """
        service = RunDiscoveryService(artifacts_root=tmp_path)
        
        # Initial discovery: empty
        runs = service.discover()
        assert len(runs) == 0
        
        # Create new run
        run_dir = tmp_path / "newly_created_run"
        run_dir.mkdir()
        run_meta = {
            "run_id": "newly_created_run",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "strategy": {"key": "inside_bar"},
            "data": {"symbols": ["NEW"], "timeframe": "M5"}
        }
        with open(run_dir / "run_meta.json", "w") as f:
            json.dump(run_meta, f)
        
        # Refresh discovery
        runs_after = service.discover()
        
        # MUST include new run
        assert len(runs_after) == 1
        assert runs_after[0].run_id == "newly_created_run"
        assert runs_after[0].symbols == ["NEW"]


class TestRunDiscoveryDiagnostics:
    """Test discovery diagnostics (counts, skip reasons)."""
    
    def test_diagnostics_track_discovered_skipped_corrupt(self, tmp_path):
        """Discovery must track counts for debugging."""
        # Create 3 runs: 1 valid, 1 corrupt, 1 no artifacts
        valid_dir = tmp_path / "valid_run"
        valid_dir.mkdir()
        with open(valid_dir / "run_meta.json", "w") as f:
            json.dump({
                "run_id": "valid_run",
                "started_at": "2025-12-16T10:00:00+00:00",
                "strategy": {"key": "inside_bar"},
                "data": {"symbols": ["VALID"], "timeframe": "M5"}
            }, f)
        
        corrupt_dir = tmp_path / "corrupt_run"
        corrupt_dir.mkdir()
        with open(corrupt_dir / "run_meta.json", "w") as f:
            f.write("{corrupt}")
        
        empty_dir = tmp_path / "empty_run"
        empty_dir.mkdir()
        # No artifacts at all
        
        service = RunDiscoveryService(artifacts_root=tmp_path)
        runs = service.discover()
        
        # Should have 2 runs: 1 valid, 1 corrupt
        # empty_dir skipped (no artifacts)
        assert len(runs) == 2
        
        # Check diagnostics
        diag = service.get_diagnostics()
        assert diag["discovered_count"] == 2
        assert diag["corrupt_count"] == 1
        assert diag["skipped_count"] == 1
        assert len(diag["skipped_reasons"]) > 0
