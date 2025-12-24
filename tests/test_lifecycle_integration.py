"""
Lifecycle Integration Tests
============================

Tests for MVP lifecycle integration of InsideBar Intraday strategy.

Per FACTORY_LABS_AND_STRATEGY_LIFECYCLE_v2.md:
- Bootstrap script creates strategy versions correctly
- Pre-PaperTrading enforces gating rules
- Strategy runs are tracked in database

MVP Scope: InsideBar Intraday only (Backtest → Pre-PaperTrading)
"""

import pytest
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import tempfile
import sys

# Add necessary paths for imports
TEST_DIR = Path(__file__).resolve().parent
ROOT = TEST_DIR.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_dashboard.repositories.strategy_metadata import (
    StrategyMetadataRepository,
    LifecycleStage,
    LabStage,
)
from strategies.profiles.inside_bar import INSIDE_BAR_V1_PROFILE


class TestBootstrapInsideBarStrategyVersion:
    """Test bootstrap script logic for creating InsideBar strategy version."""

    def test_bootstrap_creates_version_first_time(self):
        """Bootstrap creates InsideBar v1.00 strategy version on first run."""
        # Create temp database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            # Initialize repository
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Replicate bootstrap logic
            strategy_key = "insidebar_intraday"
            impl_version = 1
            profile_key = "insidebar_intraday"  # CRITICAL: NOT "default"!
            profile_version = 1
            label = "InsideBar v1.00 – Initial Stable"
            lifecycle_stage = LifecycleStage.BACKTEST_APPROVED

            # Get config from profile
            config_dict = INSIDE_BAR_V1_PROFILE.default_parameters.copy()

            # Check version doesn't exist
            existing = repo.find_strategy_version(
                strategy_key=strategy_key,
                impl_version=impl_version,
                profile_key=profile_key,
                profile_version=profile_version
            )

            assert existing is None, "Version should not exist initially"

            # Create version
            version_id = repo.create_strategy_version(
                strategy_key=strategy_key,
                impl_version=impl_version,
                label=label,
                code_ref_value="test_commit",
                config_json=config_dict,
                profile_key=profile_key,
                profile_version=profile_version,
                lifecycle_stage=lifecycle_stage,
                code_ref_type="git",
                universe_key=None
            )

            assert version_id is not None
            assert version_id > 0

            # Verify created version
            created = repo.get_strategy_version_by_id(version_id)

            assert created is not None
            assert created.strategy_key == "insidebar_intraday"
            assert created.impl_version == 1
            assert created.profile_key == "insidebar_intraday"
            assert created.profile_version == 1
            assert created.lifecycle_stage == LifecycleStage.BACKTEST_APPROVED
            assert created.label == label

        finally:
            db_path.unlink()

    def test_bootstrap_idempotent_no_duplicates(self):
        """Bootstrap is idempotent - running twice doesn't create duplicates."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            strategy_key = "insidebar_intraday"
            impl_version = 1
            profile_key = "insidebar_intraday"
            profile_version = 1

            config_dict = INSIDE_BAR_V1_PROFILE.default_parameters.copy()

            # First creation
            version_id_1 = repo.create_strategy_version(
                strategy_key=strategy_key,
                impl_version=impl_version,
                label="InsideBar v1.00 – Initial Stable",
                code_ref_value="commit1",
                config_json=config_dict,
                profile_key=profile_key,
                profile_version=profile_version,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED
            )

            # Second attempt - should find existing
            existing = repo.find_strategy_version(
                strategy_key=strategy_key,
                impl_version=impl_version,
                profile_key=profile_key,
                profile_version=profile_version
            )

            assert existing is not None
            assert existing.id == version_id_1

            # Verify only one version exists
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("""
                SELECT COUNT(*) FROM strategy_version
                WHERE strategy_key = ?
                  AND impl_version = ?
                  AND profile_key = ?
                  AND profile_version = ?
            """, (strategy_key, impl_version, profile_key, profile_version))

            count = cursor.fetchone()[0]
            conn.close()

            assert count == 1, "Should have exactly one version"

        finally:
            db_path.unlink()


class TestPrePaperGatingLogic:
    """Test Pre-PaperTrading gating rules per lifecycle requirements."""

    def test_pre_paper_requires_valid_strategy_version(self):
        """Pre-Paper rejects invalid strategy_version_id."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Try to get non-existent version
            version = repo.get_strategy_version_by_id(9999)

            assert version is None, "Non-existent version should return None"

        finally:
            db_path.unlink()

    def test_pre_paper_rejects_beta_versions(self):
        """Pre-Paper rejects beta versions (impl_version < 1)."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Create beta version (impl_version = 0)
            config_dict = {"atr_period": 14, "risk_reward_ratio": 2.0}

            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=0,  # BETA!
                label="InsideBar v0.01 – Beta",
                code_ref_value="test_commit",
                config_json=config_dict,
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.DRAFT_EXPLORE  # Still in explore
            )

            version = repo.get_strategy_version_by_id(version_id)

            # Simulate gating logic
            from trading_dashboard.services.pre_papertrade_adapter import PrePaperTradeAdapter

            adapter = PrePaperTradeAdapter()

            # Should raise ValueError for beta version
            with pytest.raises(ValueError, match="Beta version not allowed"):
                adapter._validate_strategy_version(version)

        finally:
            db_path.unlink()

    def test_pre_paper_rejects_wrong_lifecycle(self):
        """Pre-Paper rejects versions with lifecycle_stage < BACKTEST_APPROVED."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Create version with wrong lifecycle stage
            config_dict = {"atr_period": 14, "risk_reward_ratio": 2.0}

            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,  # Stable version number
                label="InsideBar v1.00 – Not Approved",
                code_ref_value="test_commit",
                config_json=config_dict,
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.DRAFT_EXPLORE  # NOT approved!
            )

            version = repo.get_strategy_version_by_id(version_id)

            # Simulate gating logic
            from trading_dashboard.services.pre_papertrade_adapter import PrePaperTradeAdapter

            adapter = PrePaperTradeAdapter()

            # Should raise ValueError for wrong lifecycle stage
            with pytest.raises(ValueError, match="not approved for Pre-PaperTrading"):
                adapter._validate_strategy_version(version)

        finally:
            db_path.unlink()

    def test_pre_paper_accepts_valid_version(self):
        """Pre-Paper accepts valid version (impl >= 1, lifecycle >= BACKTEST_APPROVED)."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Create VALID version
            config_dict = {"atr_period": 14, "risk_reward_ratio": 2.0}

            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,  # Stable
                label="InsideBar v1.00 – Approved",
                code_ref_value="test_commit",
                config_json=config_dict,
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED  # Approved!
            )

            version = repo.get_strategy_version_by_id(version_id)

            # Simulate gating logic
            from trading_dashboard.services.pre_papertrade_adapter import PrePaperTradeAdapter

            adapter = PrePaperTradeAdapter()

            # Should NOT raise any exception
            adapter._validate_strategy_version(version)

        finally:
            db_path.unlink()


class TestStrategyRunTracking:
    """Test strategy_run creation and tracking for Pre-PaperTrading."""

    def test_pre_paper_creates_strategy_run(self):
        """Pre-Paper creates strategy_run record with correct lab_stage and metrics."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Create valid strategy version
            config_dict = {"atr_period": 14, "risk_reward_ratio": 2.0}

            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,
                label="InsideBar v1.00 – Approved",
                code_ref_value="test_commit",
                config_json=config_dict,
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED
            )

            # Create strategy run
            run_id = repo.create_strategy_run(
                strategy_version_id=version_id,
                lab_stage=LabStage.PRE_PAPERTRADE,
                run_type="replay",
                environment="test",
                tags=json.dumps({"symbols": ["AAPL"], "timeframe": "M5"})
            )

            assert run_id is not None
            assert run_id > 0

            # Verify run record
            runs = repo.get_runs_for_strategy_version(version_id)

            assert len(runs) == 1
            assert runs[0].strategy_version_id == version_id
            assert runs[0].lab_stage == LabStage.PRE_PAPERTRADE
            assert runs[0].run_type == "replay"
            assert runs[0].environment == "test"
            assert runs[0].status == "running"  # Initial status

            # Update run to completed
            metrics = {
                "number_of_signals": 5,
                "symbols_requested_count": 1,
                "symbols_success_count": 1,
                "symbols_error_count": 0,
                "start_time": datetime.now().isoformat(),
                "end_time": datetime.now().isoformat(),
            }

            repo.update_strategy_run_status(
                run_id=run_id,
                status="completed",
                metrics_json=metrics
            )

            # Verify update
            runs = repo.get_runs_for_strategy_version(version_id)

            assert runs[0].status == "completed"
            assert runs[0].metrics_json is not None

            metrics_loaded = json.loads(runs[0].metrics_json)
            assert metrics_loaded["number_of_signals"] == 5
            assert metrics_loaded["symbols_requested_count"] == 1

        finally:
            db_path.unlink()

    def test_run_tracking_with_failure(self):
        """Strategy run can be marked as failed with error message."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Create version and run
            config_dict = {"atr_period": 14}

            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,
                label="InsideBar v1.00",
                code_ref_value="test",
                config_json=config_dict,
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED
            )

            run_id = repo.create_strategy_run(
                strategy_version_id=version_id,
                lab_stage=LabStage.PRE_PAPERTRADE,
                run_type="replay",
                environment="test"
            )

            # Mark as failed
            repo.update_strategy_run_status(
                run_id=run_id,
                status="failed",
                error_message="Test error: Data fetch failed",
                metrics_json={
                    "number_of_signals": 0,
                    "symbols_requested_count": 1,
                    "symbols_success_count": 0,
                    "symbols_error_count": 1,
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                }
            )

            # Verify
            runs = repo.get_runs_for_strategy_version(version_id)

            assert runs[0].status == "failed"
            assert runs[0].error_message == "Test error: Data fetch failed"
            assert runs[0].ended_at is not None

        finally:
            db_path.unlink()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
