"""Tests for StrategyConfigStore save_new_version operations."""

import pytest
import yaml
import os
from pathlib import Path
from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore


@pytest.fixture
def temp_config_root(tmp_path, monkeypatch):
    """Fixture for temporary config root."""
    config_dir = tmp_path / "configs" / "strategies"
    config_dir.mkdir(parents=True)
    
    # Set environment variable
    monkeypatch.setenv("STRATEGY_CONFIG_ROOT", str(config_dir))
    
    # Create initial YAML
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
                    "inside_bar_mode": "inclusive"
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
    
    return config_dir


def test_save_new_version_end_to_end(temp_config_root):
    """Test save_new_version creates new version and can be loaded."""
    # Save new version
    StrategyConfigStore.save_new_version(
        strategy_id="insidebar_intraday",
        base_version="1.0.0",
        new_version="1.1.0",
        core_overrides={"atr_period": 20},
        tunable_overrides={"lookback_candles": 100}
    )
    
    # Load new version
    defaults = StrategyConfigStore.get_defaults("insidebar_intraday", "1.1.0")
    
    assert defaults["version"] == "1.1.0"
    assert defaults["core"]["atr_period"] == 20
    assert defaults["tunable"]["lookback_candles"] == 100
    
    # Verify base version unchanged
    base_defaults = StrategyConfigStore.get_defaults("insidebar_intraday", "1.0.0")
    assert base_defaults["core"]["atr_period"] == 14
    assert base_defaults["tunable"]["lookback_candles"] == 50


def test_save_new_version_rejects_invalid_overrides(temp_config_root):
    """Test save_new_version rejects invalid parameter overrides."""
    # Invalid core parameter (unknown key)
    with pytest.raises(ValueError, match="unknown core key"):
        StrategyConfigStore.save_new_version(
            strategy_id="insidebar_intraday",
            base_version="1.0.0",
            new_version="2.0.0",
            core_overrides={"invalid_param": 999}
        )


def test_save_new_version_rejects_existing_version(temp_config_root):
    """Test save_new_version rejects if version already exists."""
    with pytest.raises(ValueError, match="Version '1.0.0' already exists"):
        StrategyConfigStore.save_new_version(
            strategy_id="insidebar_intraday",
            base_version="1.0.0",
            new_version="1.0.0",  # Same as base
            core_overrides={"atr_period": 20}
        )


def test_save_new_version_rejects_unregistered_strategy():
    """Test save_new_version rejects unregistered strategy_id."""
    with pytest.raises(ValueError, match="No manager registered for strategy: unknown_strategy"):
        StrategyConfigStore.save_new_version(
            strategy_id="unknown_strategy",
            base_version="1.0.0",
            new_version="2.0.0"
        )


def test_save_new_version_validates_via_spec(temp_config_root):
    """Test save_new_version validates overrides via spec constraints."""
    # Invalid type (atr_period must be int)
    with pytest.raises(ValueError):
        StrategyConfigStore.save_new_version(
            strategy_id="insidebar_intraday",
            base_version="1.0.0",
            new_version="3.0.0",
            core_overrides={"atr_period": "not_an_int"}
        )


def test_save_new_version_no_overrides_creates_copy(temp_config_root):
    """Test save_new_version with no overrides creates exact copy."""
    StrategyConfigStore.save_new_version(
        strategy_id="insidebar_intraday",
        base_version="1.0.0",
        new_version="1.0.1"
        # No overrides
    )
    
    # Load both versions
    base = StrategyConfigStore.get_defaults("insidebar_intraday", "1.0.0")
    new = StrategyConfigStore.get_defaults("insidebar_intraday", "1.0.1")
    
    # Core and tunable should be identical
    assert base["core"] == new["core"]
    assert base["tunable"] == new["tunable"]
