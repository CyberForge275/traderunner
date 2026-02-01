"""
Tests for InsideBar configuration loading from strategy-local directory.

Verifies that the configuration is loaded from src/strategies/inside_bar/
and not from the old global config/ directory.
"""
import pytest
from pathlib import Path
from src.strategies.inside_bar.config import (
    load_default_config,
    get_default_config_path,
    InsideBarConfig
)


def test_config_path_is_strategy_local():
    """Test that default config path is within the strategy directory."""
    config_path = get_default_config_path()
    
    # Verify the path is within the strategy directory
    assert "src/strategies/inside_bar" in str(config_path)
    assert config_path.name == "insidebar_intraday.yaml"
    assert config_path.exists()


def test_load_default_config_returns_dict():
    """Test that load_default_config returns a valid dictionary."""
    config = load_default_config()
    
    # Verify it's a dictionary
    assert isinstance(config, dict)
    
    # Verify it has expected keys
    expected_keys = [
        'atr_period',
        'risk_reward_ratio',
        'max_position_pct',
        'stop_distance_cap_ticks'
    ]
    for key in expected_keys:
        assert key in config, f"Expected key '{key}' not found in config"


def test_config_has_correct_defaults():
    """Test that loaded config has expected default values."""
    config = load_default_config()
    
    # Verify some critical defaults
    assert config['atr_period'] == 15
    assert config['max_position_pct'] == 100.0
    assert config['stop_distance_cap_ticks'] == 40


def test_inside_bar_config_accepts_loaded_defaults():
    """Test that InsideBarConfig can be instantiated with loaded defaults."""
    defaults = load_default_config()
    
    # Should not raise any errors
    config = InsideBarConfig(**defaults)
    
    # Verify the instance has correct attributes
    assert config.atr_period == 15
    assert config.max_position_pct == 100.0
    assert config.stop_distance_cap_ticks == 40


def test_old_global_config_path_is_not_primary():
    """Test that the old global config path is not the first choice."""
    config_path = get_default_config_path()
    
    # The path should NOT be the old global config location
    old_global_path = Path.home() / 'data' / 'workspace' / 'droid' / 'traderunner' / 'config' / 'inside_bar.yaml'
    
    # If both files exist, the strategy-local one should be chosen
    assert config_path != old_global_path or not old_global_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
