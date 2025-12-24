"""
Tests for Pre-Paper Run History UI Integration
===============================================

Validates run history panel functionality for InsideBar Pre-PaperTrading.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from trading_dashboard.repositories.strategy_metadata import (
    StrategyMetadataRepository,
    LifecycleStage,
    LabStage,
)
from trading_dashboard.utils.run_history_utils import (
    get_pre_paper_run_history,
    format_run_history_for_table,
)


class TestRunHistoryUtils:
    """Test run history utility functions."""

    def test_run_history_returns_empty_when_no_runs(self):
        """get_pre_paper_run_history returns empty list when no runs exist."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Create strategy version but no runs
            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,
                label="InsideBar v1.00",
                code_ref_value="test123",
                config_json={"atr_period": 14},
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED
            )

            # Patch get_repository
            with patch('trading_dashboard.utils.run_history_utils.get_repository', return_value=repo):
                with patch('trading_dashboard.utils.run_history_utils.resolve_pre_paper_version') as mock_resolve:
                    mock_version = Mock()
                    mock_version.id = version_id
                    mock_resolve.return_value = mock_version

                    runs = get_pre_paper_run_history("insidebar_intraday", limit=10)

            assert runs == []

        finally:
            db_path.unlink()

    def test_run_history_shows_latest_runs_first(self):
        """Runs are returned in descending order (newest first)."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Create strategy version
            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,
                label="InsideBar v1.00",
                code_ref_value="test123",
                config_json={"atr_period": 14},
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED
            )

            # Create multiple runs with different timestamps
            run_ids = []
            for i in range(3):
                run_id = repo.create_strategy_run(
                    strategy_version_id=version_id,
                    lab_stage=LabStage.PRE_PAPERTRADE,
                    run_type="replay",
                    environment="test",
                    tags=json.dumps({"symbols": ["AAPL"]})
                )
                run_ids.append(run_id)

                # Manually update started_at to create different timestamps
                conn = repo._get_connection()
                conn.execute(
                    "UPDATE strategy_run SET started_at = ? WHERE id = ?",
                    (f"2025-12-15 12:0{i}:00", run_id)
                )
                conn.commit()
                conn.close()

            # Patch get_repository
            with patch('trading_dashboard.utils.run_history_utils.get_repository', return_value=repo):
                with patch('trading_dashboard.utils.run_history_utils.resolve_pre_paper_version') as mock_resolve:
                    mock_version = Mock()
                    mock_version.id = version_id
                    mock_resolve.return_value = mock_version

                    runs = get_pre_paper_run_history("insidebar_intraday", limit=10)

            assert len(runs) == 3
            # Check order: newest first
            assert runs[0]["run_id"] == run_ids[2]  # Latest
            assert runs[1]["run_id"] == run_ids[1]
            assert runs[2]["run_id"] == run_ids[0]  # Oldest

        finally:
            db_path.unlink()

    def test_run_history_uses_pre_paper_lab_stage_only(self):
        """Only Pre-Paper runs (lab_stage=1) are included, not other stages."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Create strategy version
            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,
                label="InsideBar v1.00",
                code_ref_value="test123",
                config_json={"atr_period": 14},
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED
            )

            # Create run in PRE_PAPERTRADE
            pre_paper_run_id = repo.create_strategy_run(
                strategy_version_id=version_id,
                lab_stage=LabStage.PRE_PAPERTRADE,  # Should be included
                run_type="replay",
                environment="test",
                tags=json.dumps({"symbols": ["AAPL"]})
            )

            # Create run in BACKTEST (should NOT be included)
            repo.create_strategy_run(
                strategy_version_id=version_id,
                lab_stage=LabStage.BACKTEST,  # Should NOT be included
                run_type="backtest",
                environment="test",
                tags=json.dumps({"symbols": ["TSLA"]})
            )

            # Patch get_repository
            with patch('trading_dashboard.utils.run_history_utils.get_repository', return_value=repo):
                with patch('trading_dashboard.utils.run_history_utils.resolve_pre_paper_version') as mock_resolve:
                    mock_version = Mock()
                    mock_version.id = version_id
                    mock_resolve.return_value = mock_version

                    runs = get_pre_paper_run_history("insidebar_intraday", limit=10)

            # Only Pre-Paper run should be returned
            assert len(runs) == 1
            assert runs[0]["run_id"] == pre_paper_run_id

        finally:
            db_path.unlink()

    def test_run_history_limits_results(self):
        """Limit parameter correctly restricts number of results."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # Create strategy version
            version_id = repo.create_strategy_version(
                strategy_key="insidebar_intraday",
                impl_version=1,
                label="InsideBar v1.00",
                code_ref_value="test123",
                config_json={"atr_period": 14},
                profile_key="insidebar_intraday",
                profile_version=1,
                lifecycle_stage=LifecycleStage.BACKTEST_APPROVED
            )

            # Create 15 runs
            for i in range(15):
                repo.create_strategy_run(
                    strategy_version_id=version_id,
                    lab_stage=LabStage.PRE_PAPERTRADE,
                    run_type="replay",
                    environment="test",
                    tags=json.dumps({"symbols": ["AAPL"]})
                )

            # Patch get_repository
            with patch('trading_dashboard.utils.run_history_utils.get_repository', return_value=repo):
                with patch('trading_dashboard.utils.run_history_utils.resolve_pre_paper_version') as mock_resolve:
                    mock_version = Mock()
                    mock_version.id = version_id
                    mock_resolve.return_value = mock_version

                    # Request only 5
                    runs = get_pre_paper_run_history("insidebar_intraday", limit=5)

            assert len(runs) == 5

        finally:
            db_path.unlink()

    def test_format_run_history_for_table_returns_dict_list(self):
        """format_run_history_for_table produces table-friendly dictionaries."""
        # Mock run data
        runs = [
            {
                "run_id": 1,
                "started_at": "2025-12-15 12:00:00",
                "run_type": "replay",
                "status": "completed",
                "signals": 3,
                "symbols": "AAPL, TSLA",
                "duration_seconds": 1.5
            }
        ]

        table_data = format_run_history_for_table(runs)

        assert len(table_data) == 1
        assert "Run ID" in table_data[0]
        assert table_data[0]["Run ID"] == 1
        assert table_data[0]["Mode"] == "Replay"
        assert table_data[0]["Status"] == "✅ Completed"  # With emoji badge
        assert table_data[0]["Signals"] == 3

    def test_run_history_handles_missing_version_gracefully(self):
        """get_pre_paper_run_history returns empty list when no valid version exists."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            repo = StrategyMetadataRepository(db_path)
            repo.initialize_schema()

            # No versions created

            # Patch get_repository
            with patch('trading_dashboard.utils.run_history_utils.get_repository', return_value=repo):
                with patch('trading_dashboard.utils.run_history_utils.resolve_pre_paper_version', side_effect=ValueError("No version")):
                    runs = get_pre_paper_run_history("insidebar_intraday", limit=10)

            # Should return empty list, not crash
            assert runs == []

        finally:
            db_path.unlink()


class TestPrePaperCallbackIntegration:
    """Test Pre-Paper callback integration with run history."""

    def test_pre_paper_callback_includes_run_history_output(self):
        """Callback returns run history container in output tuple."""
        # This test validates that _build_run_history_panel is callable
        from trading_dashboard.callbacks.pre_papertrade_callbacks import _build_run_history_panel

        # Should not raise exception
        result = _build_run_history_panel("insidebar_intraday")

        # Result should be a Dash component or empty list
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
