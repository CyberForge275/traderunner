"""UI Contract tests for StrategyConfigStore - Schritt 1."""

import pytest
import yaml
import logging
from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore


@pytest.fixture
def temp_config_root(tmp_path, monkeypatch):
    """Fixture to create a temporary strategy config root and set ENV."""
    config_dir = tmp_path / "configs" / "strategies"
    config_dir.mkdir(parents=True)
    
    # Set environment variable for repository to find this dir
    monkeypatch.setenv("STRATEGY_CONFIG_ROOT", str(config_dir))
    
    return config_dir


def test_store_reads_inside_bar_defaults_from_yaml(temp_config_root):
    """Test that store correctly reads defaults from YAML when available."""
    # 1. Setup YAML (New Schema)
    content = {
        "strategy_id": "insidebar_intraday",
        "canonical_name": "inside_bar",
        "versions": {
            "2.0.0": {
                "required_warmup_bars": 250,
                "core": {
                    "atr_period": 20,
                    "risk_reward_ratio": 3.0,
                    "min_mother_bar_size": 1.0,
                    "breakout_confirmation": False,
                    "inside_bar_mode": "strict",
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
                    "lookback_candles": 100,
                    "max_pattern_age_candles": 24,
                    "max_deviation_atr": 5.0
                }
            }
        }
    }
    
    yaml_file = temp_config_root / "insidebar_intraday.yaml"
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
        
    # 2. Get defaults
    defaults = StrategyConfigStore.get_defaults("insidebar_intraday", "2.0.0")
    
    # 3. Assert
    assert defaults["strategy"] == "insidebar_intraday"
    assert defaults["version"] == "2.0.0"
    assert defaults["required_warmup_bars"] == 250
    assert defaults["core"]["atr_period"] == 20
    assert defaults["core"]["breakout_confirmation"] is False
    assert defaults["tunable"]["lookback_candles"] == 100


def test_store_rejects_strategy_id_mismatch(temp_config_root):
    """Test strict failure when YAML strategy_id doesn't match requested ID."""
    # YAML says 'other_id' but file is 'insidebar_intraday.yaml'
    content = {
        "strategy_id": "other_id",
        "versions": {"1.0.0": {"required_warmup_bars": 0, "core": {}}}
    }
    yaml_file = temp_config_root / "insidebar_intraday.yaml"
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
        
    # Should raise, not fallback
    with pytest.raises(ValueError, match="Strategy ID mismatch"):
        StrategyConfigStore.get_defaults("insidebar_intraday", "1.0.0")


def test_store_raises_on_missing_yaml(monkeypatch):
    """Test strict failure when YAML file is missing (no fallback)."""
    # Point to non-existent path
    monkeypatch.setenv("STRATEGY_CONFIG_ROOT", "/tmp/non_existent_path_12345")
    
    # Should raise, not fallback
    with pytest.raises(FileNotFoundError, match="Strategy config file not found"):
        StrategyConfigStore.get_defaults("insidebar_intraday", "2.0.0")


def test_store_raises_on_invalid_yaml(temp_config_root):
    """Test strict failure when YAML exists but is invalid."""
    # Invalid YAML: missing strategy_id
    content = {
        "versions": {
            "2.0.0": {
                "required_warmup_bars": 200,
                "core": {
                    "atr_period": 14,
                    "risk_reward_ratio": 2.0,
                    "min_mother_bar_size": 0.5,
                    "breakout_confirmation": True,
                    "inside_bar_mode": "inclusive",
                    "mystery_key": "not_allowed"
                }
            }
        }
    }
    
    yaml_file = temp_config_root / "insidebar_intraday.yaml"
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
        
    # Should raise on validation, not fallback
    with pytest.raises(ValueError, match="Strategy ID mismatch"):
        StrategyConfigStore.get_defaults("insidebar_intraday", "2.0.0")


def test_store_raises_on_unregistered_strategy():
    """Test strict failure when strategy_id is not registered."""
    with pytest.raises(ValueError, match="No manager registered for strategy: unknown_strategy"):
        StrategyConfigStore.get_defaults("unknown_strategy", "1.0.0")
