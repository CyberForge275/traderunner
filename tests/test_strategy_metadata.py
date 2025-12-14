"""
Tests for Strategy Lifecycle Metadata Repository
=================================================

Tests the strategy_version and strategy_run tables and repository CRUD operations.
"""

import pytest
import sqlite3
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from trading_dashboard.repositories.strategy_metadata import (
    StrategyMetadataRepository,
    LifecycleStage,
    LabStage,
    StrategyVersion,
    StrategyRun,
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
def repository(temp_db):
    """Create repository with initialized schema."""
    repo = StrategyMetadataRepository(temp_db)
    repo.initialize_schema()
    return repo


def test_schema_initialization(temp_db):
    """Test that schema is created correctly."""
    repo = StrategyMetadataRepository(temp_db)
    repo.initialize_schema()
    
    # Verify tables exist
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    
    # Check strategy_version table
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='strategy_version'
    """)
    assert cursor.fetchone() is not None
    
    # Check strategy_run table
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='strategy_run'
    """)
    assert cursor.fetchone() is not None
    
    # Check indexes
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND tbl_name='strategy_version'
    """)
    indexes = cursor.fetchall()
    assert len(indexes) >= 2  # At least 2 indexes
    
    conn.close()


def test_create_strategy_version(repository):
    """Test creating a strategy version."""
    config = {
        "atr_period": 14,
        "risk_reward_ratio": 2.0,
        "session_filter": ["15:00-16:00"]
    }
    
    version_id = repository.create_strategy_version(
        strategy_key="insidebar_intraday",
        impl_version=1,
        label="InsideBar v1.00 - Initial Release",
        code_ref_value="abc123def456",
        config_json=config,
        lifecycle_stage=LifecycleStage.BACKTEST_APPROVED,
    )
    
    assert version_id is not None
    assert version_id > 0


def test_get_strategy_version_by_id(repository):
    """Test retrieving strategy version by ID."""
    config = {"param1": "value1"}
    
    version_id = repository.create_strategy_version(
        strategy_key="test_strategy",
        impl_version=2,
        label="Test Strategy v2",
        code_ref_value="git_hash_xyz",
        config_json=config,
    )
    
    version = repository.get_strategy_version_by_id(version_id)
    
    assert version is not None
    assert version.id == version_id
    assert version.strategy_key == "test_strategy"
    assert version.impl_version == 2
    assert version.profile_key == "default"
    assert version.profile_version == 1
    assert version.lifecycle_stage == LifecycleStage.DRAFT_EXPLORE
    assert version.code_ref_value == "git_hash_xyz"
    assert json.loads(version.config_json) == config


def test_find_strategy_version(repository):
    """Test finding strategy version by unique identifier."""
    config = {"test": "data"}
    
    repository.create_strategy_version(
        strategy_key="insidebar_intraday",
        impl_version=3,
        profile_key="aggressive",
        profile_version=2,
        label="Aggressive Profile v2",
        code_ref_value="hash123",
        config_json=config,
    )
    
    version = repository.find_strategy_version(
        strategy_key="insidebar_intraday",
        impl_version=3,
        profile_key="aggressive",
        profile_version=2,
    )
    
    assert version is not None
    assert version.strategy_key == "insidebar_intraday"
    assert version.impl_version == 3
    assert version.profile_key == "aggressive"
    assert version.profile_version == 2


def test_unique_constraint_violation(repository):
    """Test that duplicate strategy versions raise IntegrityError."""
    config = {"param": "value"}
    
    # Create first version
    repository.create_strategy_version(
        strategy_key="test_strat",
        impl_version=1,
        label="Version 1",
        code_ref_value="hash1",
        config_json=config,
    )
    
    # Try to create duplicate
    with pytest.raises(sqlite3.IntegrityError):
        repository.create_strategy_version(
            strategy_key="test_strat",
            impl_version=1,  # Same impl_version
            label="Version 1 Duplicate",
            code_ref_value="hash2",
            config_json=config,
        )


def test_update_lifecycle_stage(repository):
    """Test updating lifecycle stage."""
    config = {}
    
    version_id = repository.create_strategy_version(
        strategy_key="test",
        impl_version=1,
        label="Test",
        code_ref_value="hash",
        config_json=config,
        lifecycle_stage=LifecycleStage.DRAFT_EXPLORE,
    )
    
    # Update to backtest approved
    repository.update_lifecycle_stage(version_id, LifecycleStage.BACKTEST_APPROVED)
    
    version = repository.get_strategy_version_by_id(version_id)
    assert version.lifecycle_stage == LifecycleStage.BACKTEST_APPROVED


def test_create_strategy_run(repository):
    """Test creating a strategy run."""
    config = {}
    
    version_id = repository.create_strategy_version(
        strategy_key="test",
        impl_version=1,
        label="Test",
        code_ref_value="hash",
        config_json=config,
    )
    
    run_id = repository.create_strategy_run(
        strategy_version_id=version_id,
        lab_stage=LabStage.BACKTEST,
        run_type="batch_backtest",
        environment="dev",
        external_run_id="bt_2025_001",
    )
    
    assert run_id is not None
    assert run_id > 0


def test_foreign_key_constraint(repository):
    """Test that invalid strategy_version_id raises FK constraint error."""
    with pytest.raises(sqlite3.IntegrityError):
        repository.create_strategy_run(
            strategy_version_id=99999,  # Doesn't exist
            lab_stage=LabStage.BACKTEST,
            run_type="test",
        )


def test_update_strategy_run_status(repository):
    """Test updating run status."""
    config = {}
    
    version_id = repository.create_strategy_version(
        strategy_key="test",
        impl_version=1,
        label="Test",
        code_ref_value="hash",
        config_json=config,
    )
    
    run_id = repository.create_strategy_run(
        strategy_version_id=version_id,
        lab_stage=LabStage.PRE_PAPERTRADE,
        run_type="replay",
    )
    
    metrics = {
        "signals_generated": 42,
        "win_rate": 0.65,
    }
    
    repository.update_strategy_run_status(
        run_id=run_id,
        status="completed",
        metrics_json=metrics,
    )
    
    # Verify update
    runs = repository.get_runs_for_strategy_version(version_id)
    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].ended_at is not None
    assert json.loads(runs[0].metrics_json) == metrics


def test_get_runs_for_strategy_version(repository):
    """Test retrieving all runs for a strategy version."""
    config = {}
    
    version_id = repository.create_strategy_version(
        strategy_key="test",
        impl_version=1,
        label="Test",
        code_ref_value="hash",
        config_json=config,
    )
    
    # Create multiple runs
    repository.create_strategy_run(
        strategy_version_id=version_id,
        lab_stage=LabStage.BACKTEST,
        run_type="batch_backtest",
    )
    
    repository.create_strategy_run(
        strategy_version_id=version_id,
        lab_stage=LabStage.PRE_PAPERTRADE,
        run_type="replay",
    )
    
    repository.create_strategy_run(
        strategy_version_id=version_id,
        lab_stage=LabStage.PRE_PAPERTRADE,
        run_type="live_session",
    )
    
    # Get all runs
    all_runs = repository.get_runs_for_strategy_version(version_id)
    assert len(all_runs) == 3
    
    # Get filtered by lab stage
    pre_papertrade_runs = repository.get_runs_for_strategy_version(
        version_id, 
        lab_stage=LabStage.PRE_PAPERTRADE
    )
    assert len(pre_papertrade_runs) == 2
    assert all(run.lab_stage == LabStage.PRE_PAPERTRADE for run in pre_papertrade_runs)


def test_multiple_strategy_versions_and_runs(repository):
    """Test complex scenario with multiple versions and runs."""
    # Create InsideBar v1
    insidebar_v1_id = repository.create_strategy_version(
        strategy_key="insidebar_intraday",
        impl_version=1,
        label="InsideBar v1",
        code_ref_value="commit_v1",
        config_json={"atr_period": 14},
        lifecycle_stage=LifecycleStage.BACKTEST_APPROVED,
    )
    
    # Create InsideBar v2
    insidebar_v2_id = repository.create_strategy_version(
        strategy_key="insidebar_intraday",
        impl_version=2,
        label="InsideBar v2",
        code_ref_value="commit_v2",
        config_json={"atr_period": 20},
        lifecycle_stage=LifecycleStage.PRE_PAPERTRADE_DONE,
    )
    
    # Create runs for v1
    repository.create_strategy_run(
        strategy_version_id=insidebar_v1_id,
        lab_stage=LabStage.BACKTEST,
        run_type="batch_backtest",
    )
    
    # Create runs for v2
    repository.create_strategy_run(
        strategy_version_id=insidebar_v2_id,
        lab_stage=LabStage.BACKTEST,
        run_type="batch_backtest",
    )
    repository.create_strategy_run(
        strategy_version_id=insidebar_v2_id,
        lab_stage=LabStage.PRE_PAPERTRADE,
        run_type="replay",
    )
    
    # Verify v1 has 1 run
    v1_runs = repository.get_runs_for_strategy_version(insidebar_v1_id)
    assert len(v1_runs) == 1
    
    # Verify v2 has 2 runs
    v2_runs = repository.get_runs_for_strategy_version(insidebar_v2_id)
    assert len(v2_runs) == 2


def test_config_hash_calculation(repository):
    """Test that config hash is calculated correctly."""
    config1 = {"a": 1, "b": 2}
    config2 = {"b": 2, "a": 1}  # Same content, different order
    
    v1_id = repository.create_strategy_version(
        strategy_key="test1",
        impl_version=1,
        label="Test 1",
        code_ref_value="hash",
        config_json=config1,
    )
    
    v2_id = repository.create_strategy_version(
        strategy_key="test2",
        impl_version=1,
        label="Test 2",
        code_ref_value="hash",
        config_json=config2,
    )
    
    v1 = repository.get_strategy_version_by_id(v1_id)
    v2 = repository.get_strategy_version_by_id(v2_id)
    
    # Same config content (regardless of order) = same hash
    assert v1.config_hash == v2.config_hash
