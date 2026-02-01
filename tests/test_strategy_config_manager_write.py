"""Tests for StrategyConfigManager add_version operations."""

import pytest
import yaml
from pathlib import Path
from src.strategies.config.repository import StrategyConfigRepository
from src.strategies.config.managers.inside_bar_manager import InsideBarConfigManager


@pytest.fixture
def temp_repo(tmp_path):
    """Fixture with existing insidebar_intraday.yaml."""
    config_dir = tmp_path / "configs" / "strategies"
    config_dir.mkdir(parents=True)
    
    # Create initial YAML with base version
    content = {
        "strategy_id": "insidebar_intraday",
        "canonical_name": "inside_bar",
        "versions": {
            "1.0.0": {
                "required_warmup_bars": 200,
                "core": {
                    "atr_period": 14,
                    "risk_reward_ratio": 2.0,
                    "min_mother_bar_size": 0.5,
                    "breakout_confirmation": True,
                    "inside_bar_mode": "inclusive",
                    "session_timezone": "America/New_York",
                    "session_mode": "rth",
                    "session_filter": ["09:30-16:00"],
                    "timeframe_minutes": 5,
                    "valid_from_policy": "signal_ts",
                    "order_validity_policy": "session_end",
                    "stop_distance_cap_ticks": 40,
                    "max_position_pct": 100.0
                },
                "tunable": {
                    "lookback_candles": 50,
                    "max_pattern_age_candles": 12,
                    "max_deviation_atr": 3.0
                }
            }
        }
    }
    
    yaml_file = config_dir / "insidebar_intraday.yaml"
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
    
    repo = StrategyConfigRepository(base_path=config_dir)
    return repo, config_dir


def test_add_version_creates_new_without_mutating_base(temp_repo):
    """Test add_version creates new version without changing base."""
    repo, config_dir = temp_repo
    manager = InsideBarConfigManager(repository=repo)
    
    # Add new version with override
    manager.add_version(
        base_version="1.0.0",
        new_version="1.1.0",
        overrides_core={"atr_period": 20}
    )
    
    # Load YAML and verify
    yaml_file = config_dir / "insidebar_intraday.yaml"
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    
    # Base version unchanged
    assert content["versions"]["1.0.0"]["core"]["atr_period"] == 14
    
    # New version has override
    assert "1.1.0" in content["versions"]
    assert content["versions"]["1.1.0"]["core"]["atr_period"] == 20
    
    # Other params copied from base
    assert content["versions"]["1.1.0"]["core"]["risk_reward_ratio"] == 2.0
    assert content["versions"]["1.1.0"]["tunable"]["lookback_candles"] == 50


def test_add_version_rejects_existing_version(temp_repo):
    """Test add_version rejects if new_version already exists."""
    repo, _ = temp_repo
    manager = InsideBarConfigManager(repository=repo)
    
    with pytest.raises(ValueError, match="Version '1.0.0' already exists"):
        manager.add_version(
            base_version="1.0.0",
            new_version="1.0.0",  # Same as base
            overrides_core={"atr_period": 20}
        )


def test_add_version_rejects_missing_base(temp_repo):
    """Test add_version rejects if base_version doesn't exist."""
    repo, _ = temp_repo
    manager = InsideBarConfigManager(repository=repo)
    
    with pytest.raises(ValueError, match="Base version '9.9.9' not found"):
        manager.add_version(
            base_version="9.9.9",
            new_version="10.0.0"
        )


def test_add_version_validates_overrides(temp_repo):
    """Test add_version validates overrides via spec."""
    repo, _ = temp_repo
    manager = InsideBarConfigManager(repository=repo)
    
    # Invalid override (unknown key)
    with pytest.raises(ValueError, match="unknown core key"):
        manager.add_version(
            base_version="1.0.0",
            new_version="1.1.0",
            overrides_core={"invalid_key": 123}
        )


def test_add_version_applies_tunable_overrides(temp_repo):
    """Test add_version correctly applies tunable overrides."""
    repo, config_dir = temp_repo
    manager = InsideBarConfigManager(repository=repo)
    
    manager.add_version(
        base_version="1.0.0",
        new_version="2.0.0",
        overrides_tunable={"lookback_candles": 100}
    )
    
    yaml_file = config_dir / "insidebar_intraday.yaml"
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    
    # Base unchanged
    assert content["versions"]["1.0.0"]["tunable"]["lookback_candles"] == 50
    
    # New version has override
    assert content["versions"]["2.0.0"]["tunable"]["lookback_candles"] == 100
    
    # Core params copied
    assert content["versions"]["2.0.0"]["core"]["atr_period"] == 14


def test_add_version_atomic_write(temp_repo):
    """Test add_version writes atomically (file valid after write)."""
    repo, config_dir = temp_repo
    manager = InsideBarConfigManager(repository=repo)
    
    manager.add_version(
        base_version="1.0.0",
        new_version="3.0.0",
        overrides_core={"atr_period": 30}
    )
    
    # Verify file is parseable
    yaml_file = config_dir / "insidebar_intraday.yaml"
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    
    assert content["strategy_id"] == "insidebar_intraday"
    assert "3.0.0" in content["versions"]
    
    # Can load via manager
    loaded = manager.get_version("3.0.0")
    assert loaded["core"]["atr_period"] == 30


def test_add_version_preserves_all_existing_versions(temp_repo):
    """Test add_version doesn't remove or modify other versions."""
    repo, config_dir = temp_repo
    manager = InsideBarConfigManager(repository=repo)
    
    # Add v2.0.0
    manager.add_version(
        base_version="1.0.0",
        new_version="2.0.0",
        overrides_core={"atr_period": 20}
    )
    
    # Add v3.0.0 based on v1.0.0 (not v2.0.0)
    manager.add_version(
        base_version="1.0.0",
        new_version="3.0.0",
        overrides_core={"atr_period": 30}
    )
    
    yaml_file = config_dir / "insidebar_intraday.yaml"
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    
    # All three versions exist
    assert "1.0.0" in content["versions"]
    assert "2.0.0" in content["versions"]
    assert "3.0.0" in content["versions"]
    
    # Each has correct atr_period
    assert content["versions"]["1.0.0"]["core"]["atr_period"] == 14
    assert content["versions"]["2.0.0"]["core"]["atr_period"] == 20
    assert content["versions"]["3.0.0"]["core"]["atr_period"] == 30
