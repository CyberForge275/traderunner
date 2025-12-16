"""
Tests for ArtifactsManager

Verifies fail-safe artifact creation in all scenarios.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from backtest.services.artifacts_manager import ArtifactsManager
from backtest.services.run_status import RunResult, RunStatus, FailureReason
from backtest.services.data_coverage import CoverageCheckResult, CoverageStatus, DateRange
import pandas as pd


class TestArtifactsManager:
    """Test artifacts manager fail-safe behavior."""
    
    def test_create_run_dir_always_succeeds(self, tmp_path):
        """Verify run directory is always created."""
        artifacts_root = tmp_path / "artifacts" / "backtests"
        manager = ArtifactsManager(artifacts_root=artifacts_root)
        
        run_id = "test_run_123"
        run_dir = manager.create_run_dir(run_id)
        
        assert run_dir.exists()
        assert run_dir.is_dir()
        assert run_dir.name == run_id
    
    def test_run_meta_written_at_start(self, tmp_path):
        """Verify run_meta.json is written before execution."""
        artifacts_root = tmp_path / "artifacts" / "backtests"
        manager = ArtifactsManager(artifacts_root=artifacts_root)
        
        run_id = "test_run_meta"
        manager.create_run_dir(run_id)
        
        manager.write_run_meta(
            strategy="inside_bar",
            symbols=["HOOD"],
            timeframe="M15",
            params={"atr_period": 14},
            requested_end="2025-12-12",
            lookback_days=100,
            commit_hash="abc123"
        )
        
        meta_path = manager.get_run_dir() / "run_meta.json"
        assert meta_path.exists()
        
        with open(meta_path) as f:
            meta = json.load(f)
        
        assert meta["run_id"] == run_id
        assert meta["strategy"]["key"] == "inside_bar"
        assert meta["data"]["symbols"] == ["HOOD"]
        assert meta["data"]["timeframe"] == "M15"
        assert meta["commit_hash"] == "abc123"
    
    def test_run_result_always_written_on_success(self, tmp_path):
        """Verify run_result.json is written on SUCCESS."""
        artifacts_root = tmp_path / "artifacts" / "backtests"
        manager = ArtifactsManager(artifacts_root=artifacts_root)
        
        run_id = "test_success"
        manager.create_run_dir(run_id)
        
        result = RunResult(
            run_id=run_id,
            status=RunStatus.SUCCESS,
            details={"signals": 42}
        )
        
        manager.write_run_result(result)
        
        result_path = manager.get_run_dir() / "run_result.json"
        assert result_path.exists()
        
        with open(result_path) as f:
            result_data = json.load(f)
        
        assert result_data["status"] == "success"
        assert result_data["reason"] is None
        assert result_data["details"]["signals"] == 42
    
    def test_run_result_written_on_failed_precondition(self, tmp_path):
        """Verify run_result.json is written on FAILED_PRECONDITION."""
        artifacts_root = tmp_path / "artifacts" / "backtests"
        manager = ArtifactsManager(artifacts_root=artifacts_root)
        
        run_id = "test_failed_precondition"
        manager.create_run_dir(run_id)
        
        result = RunResult(
            run_id=run_id,
            status=RunStatus.FAILED_PRECONDITION,
            reason=FailureReason.DATA_COVERAGE_GAP,
            details={
                "requested_range": {"start": "2025-09-03", "end": "2025-12-12"},
                "cached_range": {"start": "2025-09-01", "end": "2025-12-05"},
                "gap": {"start": "2025-12-05", "end": "2025-12-12"}
            }
        )
        
        manager.write_run_result(result)
        
        result_path = manager.get_run_dir() / "run_result.json"
        assert result_path.exists()
        
        with open(result_path) as f:
            result_data = json.load(f)
        
        assert result_data["status"] == "failed_precondition"
        assert result_data["reason"] == "data_coverage_gap"
        assert "requested_range" in result_data["details"]
    
    def test_run_result_written_on_error(self, tmp_path):
        """Verify run_result.json is written on ERROR."""
        artifacts_root = tmp_path / "artifacts" / "backtests"
        manager = ArtifactsManager(artifacts_root=artifacts_root)
        
        run_id = "test_error"
        manager.create_run_dir(run_id)
        
        error_id = "ABC123DEF456"
        result = RunResult(
            run_id=run_id,
            status=RunStatus.ERROR,
            error_id=error_id,
            details={"exception": "UnboundLocalError"}
        )
        
        manager.write_run_result(result)
        
        result_path = manager.get_run_dir() / "run_result.json"
        assert result_path.exists()
        
        with open(result_path) as f:
            result_data = json.load(f)
        
        assert result_data["status"] == "error"
        assert result_data["error_id"] == error_id
    
    def test_error_stacktrace_written_on_error(self, tmp_path):
        """Verify error_stacktrace.txt is written on ERROR."""
        artifacts_root = tmp_path / "artifacts" / "backtests"
        manager = ArtifactsManager(artifacts_root=artifacts_root)
        
        run_id = "test_stacktrace"
        manager.create_run_dir(run_id)
        
        # Simulate exception
        try:
            raise ValueError("Test exception for stacktrace")
        except ValueError as e:
            error_id = "TEST_ERROR_123"
            manager.write_error_stacktrace(e, error_id)
        
        stacktrace_path = manager.get_run_dir() / "error_stacktrace.txt"
        assert stacktrace_path.exists()
        
        with open(stacktrace_path) as f:
            stacktrace = f.read()
        
        assert f"Error ID: {error_id}" in stacktrace
        assert "ValueError" in stacktrace
        assert "Test exception for stacktrace" in stacktrace
        assert "Traceback" in stacktrace or "Stacktrace" in stacktrace
    
    def test_coverage_check_result_written(self, tmp_path):
        """Verify coverage_check.json is written."""
        artifacts_root = tmp_path / "artifacts" / "backtests"
        manager = ArtifactsManager(artifacts_root=artifacts_root)
        
        run_id = "test_coverage"
        manager.create_run_dir(run_id)
        
        coverage_result = CoverageCheckResult(
            status=CoverageStatus.GAP_DETECTED,
            requested_range=DateRange(
                start=pd.Timestamp("2025-09-03", tz="America/New_York"),
                end=pd.Timestamp("2025-12-12", tz="America/New_York")
            ),
            cached_range=DateRange(
                start=pd.Timestamp("2025-09-01", tz="America/New_York"),
                end=pd.Timestamp("2025-12-05", tz="America/New_York")
            ),
            gap=DateRange(
                start=pd.Timestamp("2025-12-05", tz="America/New_York"),
                end=pd.Timestamp("2025-12-12", tz="America/New_York")
            )
        )
        
        manager.write_coverage_check_result(coverage_result)
        
        coverage_path = manager.get_run_dir() / "coverage_check.json"
        assert coverage_path.exists()
        
        with open(coverage_path) as f:
            coverage_data = json.load(f)
        
        assert coverage_data["status"] == "gap_detected"
        assert coverage_data["requested_range"] is not None


class TestArtifactsManagerFailSafe:
    """Test fail-safe behavior - artifacts created even on errors."""
    
    def test_artifacts_created_even_if_execution_crashes(self, tmp_path):
        """
        Integration test: Verify artifacts exist even if execution crashes.
        
        Simulates:
        1. create_run_dir() ✅
        2. write_run_meta() ✅
        3. [CRASH during execution]
        4. write_run_result() ✅ (in finally block)
        5. write_error_stacktrace() ✅
        """
        artifacts_root = tmp_path / "artifacts" / "backtests"
        manager = ArtifactsManager(artifacts_root=artifacts_root)
        
        run_id = "test_crash_scenario"
        
        try:
            # 1. Create run dir (always first)
            manager.create_run_dir(run_id)
            
            # 2. Write meta (before execution)
            manager.write_run_meta(
                strategy="inside_bar",
                symbols=["HOOD"],
                timeframe="M15",
                params={},
                requested_end="2025-12-12",
                lookback_days=100
            )
            
            # 3. Simulate crash
            raise RuntimeError("Simulated execution crash")
        
        except Exception as e:
            # 4. Write error result (in finally/except)
            error_id = "CRASH_TEST_123"
            result = RunResult(
                run_id=run_id,
                status=RunStatus.ERROR,
                error_id=error_id,
                details={"exception": str(e)}
            )
            manager.write_run_result(result)
            manager.write_error_stacktrace(e, error_id)
        
        # 5. Verify ALL artifacts exist
        run_dir = manager.get_run_dir()
        assert (run_dir / "run_meta.json").exists()
        assert (run_dir / "run_result.json").exists()
        assert (run_dir / "error_stacktrace.txt").exists()
        
        # Verify run_result status
        with open(run_dir / "run_result.json") as f:
            result_data = json.load(f)
        assert result_data["status"] == "error"
        assert result_data["error_id"] == "CRASH_TEST_123"
