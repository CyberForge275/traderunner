"""
Integration Tests for Pipeline Coverage Gate

Tests the full pipeline flow:
1. Coverage gate detects gap → FAILED_PRECONDITION
2. Coverage gate passes → continue to execution
3. Artifacts created in all scenarios
"""

import pytest
from pathlib import Path

from backtest.examples.minimal_pipeline import minimal_backtest_with_gates
from backtest.services.run_status import RunStatus, FailureReason


class TestPipelineIntegration:
    """Integration tests for coverage gate in pipeline."""

    def test_coverage_gap_returns_failed_precondition(self, tmp_path):
        """
        Integration test: Coverage gap → FAILED_PRECONDITION

        Verifies:
        - Status = FAILED_PRECONDITION (not ERROR)
        - Reason = DATA_COVERAGE_GAP
        - Artifacts created
        - run_result.json exists with correct status
        """
        result = minimal_backtest_with_gates(
            run_id="test_gap_001",
            symbol="NONEXISTENT_SYMBOL",  # Will trigger gap
            timeframe="M15",
            requested_end="2025-12-12",
            lookback_days=100,
            strategy_params={"atr_period": 14},
            artifacts_root=tmp_path
        )

        # Verify status
        assert result.status == RunStatus.FAILED_PRECONDITION
        assert result.reason == FailureReason.DATA_COVERAGE_GAP
        assert result.error_id is None  # Not an ERROR

        # Verify artifacts
        run_dir = tmp_path / "test_gap_001"
        assert run_dir.exists()
        assert (run_dir / "run_meta.json").exists()
        assert (run_dir / "run_result.json").exists()
        assert (run_dir / "coverage_check.json").exists()

        # Verify NO error_stacktrace (this is not an ERROR)
        assert not (run_dir / "error_stacktrace.txt").exists()

    def test_artifacts_always_created_on_failed_precondition(self, tmp_path):
        """Verify artifacts are created even on FAILED_PRECONDITION."""
        result = minimal_backtest_with_gates(
            run_id="test_artifacts_fp_001",
            symbol="NONEXISTENT",
            timeframe="M15",
            requested_end="2025-12-12",
            lookback_days=100,
            strategy_params={},
            artifacts_root=tmp_path
        )

        assert result.status == RunStatus.FAILED_PRECONDITION

        # ALL artifacts must exist
        run_dir = tmp_path / "test_artifacts_fp_001"
        assert (run_dir / "run_meta.json").exists(), "run_meta.json missing"
        assert (run_dir / "run_result.json").exists(), "run_result.json missing"
        assert (run_dir / "coverage_check.json").exists(), "coverage_check.json missing"

    def test_run_result_json_always_exists(self, tmp_path):
        """
        Critical test: run_result.json MUST exist in all scenarios.

        This is the audit trail - must always be written.
        """
        result = minimal_backtest_with_gates(
            run_id="test_run_result_001",
            symbol="ANY",
            timeframe="M15",
            requested_end="2025-12-12",
            lookback_days=100,
            strategy_params={},
            artifacts_root=tmp_path
        )

        # Regardless of status, run_result.json must exist
        run_dir = tmp_path / "test_run_result_001"
        result_path = run_dir / "run_result.json"

        assert result_path.exists(), "run_result.json MUST ALWAYS exist"

        # Verify it's valid JSON with required fields
        import json
        with open(result_path) as f:
            result_data = json.load(f)

        assert "run_id" in result_data
        assert "finished_at" in result_data
        assert "status" in result_data
        assert result_data["status"] in ["success", "failed_precondition", "error"]


class TestPipelineErrorHandling:
    """Test pipeline error handling with artifacts."""

    def test_unhandled_exception_returns_error_status(self, tmp_path):
        """
        Verify unhandled exceptions result in ERROR status.

        Note: In this minimal example, we can't easily trigger an
        unhandled exception. This would happen in real pipeline
        if strategy execution crashes.
        """
        # This test is a placeholder for the real pipeline integration
        # In the real execution, if strategy crashes, we get ERROR
        pass

    def test_error_stacktrace_written_on_error(self, tmp_path):
        """Verify error_stacktrace.txt is written on ERROR status."""
        # This test is a placeholder
        # In real pipeline, if exception occurs during strategy execution,
        # error_stacktrace.txt should be written
        pass


# Run example
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
