"""
Tests for RunContext DTO and ArtifactsManager integration.

RED tests to drive RunContext implementation.
"""

import pytest
from pathlib import Path
from backtest.services.run_context import RunContext
from backtest.services.artifacts_manager import ArtifactsManager


class TestRunContextDTO:
    """Test RunContext creation and validation."""

    def test_run_context_is_frozen(self, tmp_path):
        """RunContext must be immutable (frozen dataclass)."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()  # Create directory first

        ctx = RunContext(
            run_id="test_run",
            run_name="test_run",
            run_dir=run_dir.absolute()
        )

        # Should raise FrozenInstanceError or similar
        with pytest.raises(Exception):  # dataclass frozen raises on mutation
            ctx.run_id = "modified"

    def test_run_context_requires_absolute_path(self, tmp_path):
        """run_dir must be absolute path."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Relative path should fail
        with pytest.raises(ValueError, match="must be absolute"):
            RunContext(
                run_id="test",
                run_name="test",
                run_dir=Path("relative/path")
            )

    def test_run_context_requires_existing_directory(self, tmp_path):
        """run_dir must exist when RunContext is created."""
        non_existent = tmp_path / "does_not_exist"

        with pytest.raises(ValueError, match="must exist"):
            RunContext(
                run_id="test",
                run_name="test",
                run_dir=non_existent.absolute()
            )


class TestArtifactsManagerReturnsRunContext:
    """Test that ArtifactsManager.create_run_dir returns RunContext."""

    def test_create_run_dir_returns_context_with_existing_run_dir(self, tmp_path):
        """
        RED TEST: create_run_dir must return RunContext with valid run_dir.

        This will fail until we modify ArtifactsManager to return RunContext.
        """
        manager = ArtifactsManager(artifacts_root=tmp_path)

        # This should return RunContext, not None
        ctx = manager.create_run_dir("test_run_123")

        assert isinstance(ctx, RunContext)
        assert ctx.run_id == "test_run_123"
        assert ctx.run_name == "test_run_123"
        assert ctx.run_dir.exists()
        assert ctx.run_dir.is_absolute()
        assert str(ctx.run_dir).endswith("test_run_123")

    def test_context_run_dir_is_usable_for_step_tracker(self, tmp_path):
        """
        RED TEST: RunContext.run_dir can be passed to StepTracker.

        This ensures the contract: StepTracker(ctx.run_dir) works.
        """
        manager = ArtifactsManager(artifacts_root=tmp_path)
        ctx = manager.create_run_dir("test_run_456")

        # Should not raise AttributeError
        from backtest.services.step_tracker import StepTracker
        tracker = StepTracker(ctx.run_dir)

        assert tracker.run_dir == ctx.run_dir
        assert tracker.steps_file.parent == ctx.run_dir


class TestPipelineUsesRunContext:
    """Test that minimal_pipeline uses RunContext throughout."""

    def test_minimal_pipeline_bootstrap_error_writes_run_result(self, tmp_path):
        """
        RED TEST: If pipeline fails AFTER create_run_dir but BEFORE any gates,
        it must still write run_result.json and error_stacktrace.txt.

        This prevents empty run directories (current bug on INT).
        """
        from backtest.examples.minimal_pipeline import minimal_backtest_with_gates
        from backtest.services.artifacts_manager import RunStatus

        # Simulate a coverage gap (data not available)
        # This should create run dir, check coverage, then fail with FAILED_PRECONDITION
        result = minimal_backtest_with_gates(
            run_id="bootstrap_error_test",
            symbol="INVALID_SYMBOL_THAT_CAUSES_ERROR",
            timeframe="M5",
            requested_end="2025-12-16",
            lookback_days=2,
            strategy_params={},
            artifacts_root=tmp_path
        )

        # Coverage gap = FAILED_PRECONDITION (not ERROR - this is expected behavior)
        assert result.status in [RunStatus.FAILED_PRECONDITION, RunStatus.ERROR]

        # Run directory should exist (ArtifactsManager creates directly, not under backtests/)
        run_dir = tmp_path / "bootstrap_error_test"
        assert run_dir.exists()

        # MUST have artifacts (not empty dir) - THIS IS THE KEY TEST
        assert (run_dir / "run_result.json").exists(), "run_result.json must exist even on failure"

        # Should have some artifacts written
        files = list(run_dir.glob("*"))
        assert len(files) >= 1, f"Directory should not be empty, found: {[f.name for f in files]}"
