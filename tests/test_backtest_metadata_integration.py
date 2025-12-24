"""
Tests for Backtest Lab Integration with Strategy Lifecycle Metadata
=====================================================================

Tests Phase 1 integration: Backtest → strategy_version + strategy_run
"""

import pytest
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import Mock, patch, MagicMock

from trading_dashboard.repositories.strategy_metadata import (
    StrategyMetadataRepository,
    LifecycleStage,
    LabStage,
)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def repo(temp_db):
    """Create repository with initialized schema."""
    repo = StrategyMetadataRepository(temp_db)
    repo.initialize_schema()
    return repo


def test_backtest_creates_strategy_version(temp_db):
    """Test that running a backtest creates strategy_version if not exists."""
    from trading_dashboard.services.pipeline_adapter import DashboardPipelineAdapter

    adapter = DashboardPipelineAdapter()
    repo = StrategyMetadataRepository(temp_db)
    repo.initialize_schema()

    # Test _resolve_or_create_strategy_version
    with patch.object(adapter, '_get_git_commit_hash', return_value='abc123'):
        version_id = adapter._resolve_or_create_strategy_version(
            repo=repo,
            strategy_name="inside_bar",
            config={"initial_cash": 100000, "mode": "test"},
            symbols=["AAPL", "MSFT"],
        )

    assert version_id is not None
    assert version_id > 0

    # Verify version was created
    version = repo.get_strategy_version_by_id(version_id)
    assert version is not None
    assert version.strategy_key == "inside_bar"
    assert version.impl_version == 1
    assert version.profile_key == "default"
    assert version.profile_version == 1
    assert version.lifecycle_stage == LifecycleStage.DRAFT_EXPLORE
    assert version.code_ref_value == "abc123"
    assert "initial_cash" in version.config_json


def test_backtest_reuses_existing_version(temp_db):
    """Test that backtest reuses existing strategy_version."""
    from trading_dashboard.services.pipeline_adapter import DashboardPipelineAdapter

    adapter = DashboardPipelineAdapter()
    repo = StrategyMetadataRepository(temp_db)
    repo.initialize_schema()

    config = {"initial_cash": 50000}

    # First call - creates version
    with patch.object(adapter, '_get_git_commit_hash', return_value='xyz789'):
        version_id_1 = adapter._resolve_or_create_strategy_version(
            repo=repo,
            strategy_name="rudometkin_moc",
            config=config,
            symbols=["SPY"],
        )

    # Second call - should reuse
    with patch.object(adapter, '_get_git_commit_hash', return_value='different_hash'):
        version_id_2 = adapter._resolve_or_create_strategy_version(
            repo=repo,
            strategy_name="rudometkin_moc",
            config=config,
            symbols=["QQQ"],  # Different symbols should still reuse version
        )

    # Should be the same version
    assert version_id_1 == version_id_2

    # Verify only one version exists
    all_rows = repo._get_connection().execute(
        "SELECT COUNT(*) FROM strategy_version WHERE strategy_key = 'rudometkin_moc'"
    ).fetchone()[0]
    assert all_rows == 1


def test_git_commit_hash_extraction():
    """Test Git commit hash extraction."""
    from trading_dashboard.services.pipeline_adapter import DashboardPipelineAdapter

    adapter = DashboardPipelineAdapter()

    # Should return None or a hash (depending on whether we're in a Git repo)
    result = adapter._get_git_commit_hash()

    # If in Git repo, should be 8 chars
    if result:
        assert len(result) ==  8
        assert result.isalnum()


def test_backtest_metrics_extraction(tmp_path):
    """Test extraction of backtest metrics from run_log.json."""
    from trading_dashboard.services.pipeline_adapter import DashboardPipelineAdapter

    adapter = DashboardPipelineAdapter()

    # Create mock backtest directory structure
    backtests_dir = tmp_path / "artifacts" / "backtests"
    backtests_dir.mkdir(parents=True)

    run_name = "test_run_001"
    run_dir = backtests_dir / run_name
    run_dir.mkdir()

    # Create run_log.json
    run_log = {
        "run_name": run_name,
        "status": "success",
        "strategy": "inside_bar",
        "symbols": ["AAPL", "MSFT"],
        "timeframe": "M5",
    }

    run_log_path = run_dir / "run_log.json"
    run_log_path.write_text(json.dumps(run_log))

    # Mock ROOT to point to tmp_path
    with patch('trading_dashboard.services.pipeline_adapter.ROOT', tmp_path):
        metrics = adapter._extract_backtest_metrics(run_name)

    assert metrics["run_name"] == run_name
    assert metrics["status"] == "success"
    assert metrics["strategy"] == "inside_bar"
    assert "AAPL" in metrics["symbols"]


def test_backtest_metadata_integration_mock(temp_db):
    """
    Test full backtest metadata integration with mocked execute_pipeline.

    This tests the integration without actually running a backtest.
    """
    from trading_dashboard.services.pipeline_adapter import DashboardPipelineAdapter

    # Initialize repo
    repo = StrategyMetadataRepository(temp_db)
    repo.initialize_schema()

    adapter = DashboardPipelineAdapter()

    # Mock execute_pipeline to return success
    mock_run_name = "test_backtest_20251214"

    with patch('trading_dashboard.services.pipeline_adapter.ROOT', Path("/tmp")):
        with patch('apps.streamlit.pipeline.execute_pipeline', return_value=mock_run_name):
            with patch('apps.streamlit.state.STRATEGY_REGISTRY', {
                'inside_bar': Mock(
                    strategy_name='inside_bar',
                    default_payload={'initial_cash': 100000, 'mode': 'test'},
                )
            }):
                with patch.object(adapter, '_get_git_commit_hash', return_value='abc123'):
                    with patch.object(adapter, '_extract_backtest_metrics', return_value={'total_trades': 42}):
                        # Mock the get_repository to use our temp_db
                        with patch('trading_dashboard.repositories.strategy_metadata.get_repository', return_value=repo):
                            result = adapter.execute_backtest(
                                run_name="test_bt",
                                strategy="inside_bar",
                                symbols=["AAPL"],
                                timeframe="M5",
                                start_date="2025-01-01",
                                end_date="2025-01-31",
                            )

    # Verify result contains metadata IDs
    assert result["status"] == "completed"
    assert "strategy_version_id" in result
    assert "strategy_run_id" in result

    # Verify strategy_version was created
    version = repo.get_strategy_version_by_id(result["strategy_version_id"])
    assert version is not None
    assert version.strategy_key == "inside_bar"
    assert version.lifecycle_stage == LifecycleStage.DRAFT_EXPLORE

    # Verify strategy_run was created and updated
    runs = repo.get_runs_for_strategy_version(result["strategy_version_id"])
    assert len(runs) == 1
    assert runs[0].lab_stage == LabStage.BACKTEST
    assert runs[0].status == "completed"
    assert runs[0].external_run_id == "test_bt"

    # Verify metrics were stored
    metrics = json.loads(runs[0].metrics_json)
    assert metrics["total_trades"] == 42


def test_backtest_metadata_survives_pipeline_failure(temp_db):
    """Test that strategy_run is marked as failed when pipeline fails."""
    from trading_dashboard.services.pipeline_adapter import DashboardPipelineAdapter

    repo = StrategyMetadataRepository(temp_db)
    repo.initialize_schema()

    adapter  = DashboardPipelineAdapter()

    # Mock execute_pipeline to raise an exception
    with patch('trading_dashboard.services.pipeline_adapter.ROOT', Path("/tmp")):
        with patch('apps.streamlit.pipeline.execute_pipeline', side_effect=RuntimeError("Pipeline failed")):
            with patch('apps.streamlit.state.STRATEGY_REGISTRY', {
                'inside_bar': Mock(
                    strategy_name='inside_bar',
                    default_payload={'initial_cash': 100000},
                )
            }):
                with patch.object(adapter, '_get_git_commit_hash', return_value='xyz'):
                    # Mock get_repository at import location
                    with patch('trading_dashboard.repositories.strategy_metadata.get_repository', return_value=repo):
                        result = adapter.execute_backtest(
                            run_name="failing_bt",
                            strategy="inside_bar",
                            symbols=["SPY"],
                            timeframe="M15",
                            start_date=None,
                            end_date=None,
                        )

    # Verify result shows failure
    assert result["status"] == "failed"
    assert "RuntimeError" in result["error"]

    # Verify strategy_run was marked as failed
    if result.get("strategy_run_id"):
        runs = repo.get_runs_for_strategy_version(result["strategy_version_id"])
        assert len(runs) == 1
        assert runs[0].status == "failed"
        assert "RuntimeError" in runs[0].error_message


def test_multiple_backtests_same_strategy(temp_db):
    """Test that multiple backtests of same strategy reuse version but create separate runs."""
    from trading_dashboard.services.pipeline_adapter import DashboardPipelineAdapter

    repo = StrategyMetadataRepository(temp_db)
    repo.initialize_schema()

    adapter = DashboardPipelineAdapter()

    with patch('trading_dashboard.services.pipeline_adapter.ROOT', Path("/tmp")):
        with patch('apps.streamlit.pipeline.execute_pipeline', return_value="run_001"):
            with patch('apps.streamlit.state.STRATEGY_REGISTRY', {
                'inside_bar': Mock(
                    strategy_name='inside_bar',
                    default_payload={'initial_cash': 100000},
                )
            }):
                with patch.object(adapter, '_get_git_commit_hash', return_value='commit1'):
                    with patch.object(adapter, '_extract_backtest_metrics', return_value={}):
                        # Mock get_repository at import location
                        with patch('trading_dashboard.repositories.strategy_metadata.get_repository', return_value=repo):
                            # First backtest
                            result1 = adapter.execute_backtest(
                                run_name="bt1",
                                strategy="inside_bar",
                                symbols=["AAPL"],
                                timeframe="M5",
                                start_date=None,
                                end_date=None,
                            )

                            # Second backtest (same strategy, different run)
                            result2 = adapter.execute_backtest(
                                run_name="bt2",
                                strategy="inside_bar",
                                symbols=["MSFT"],
                                timeframe="M5",
                                start_date=None,
                                end_date=None,
                            )

    # Both should succeed
    assert result1["status"] == "completed"
    assert result2["status"] == "completed"

    # Should reuse same strategy_version
    assert result1["strategy_version_id"] == result2["strategy_version_id"]

    # Should have created 2 separate runs
    runs = repo.get_runs_for_strategy_version(result1["strategy_version_id"])
    assert len(runs) == 2
    assert {run.external_run_id for run in runs} == {"bt1", "bt2"}
