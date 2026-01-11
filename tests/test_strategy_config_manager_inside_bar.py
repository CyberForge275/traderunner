"""Tests for InsideBarConfigManager - Schritt 0."""

import pytest
import yaml
from pathlib import Path
from src.strategies.config.repository import StrategyConfigRepository
from src.strategies.config.managers.inside_bar_manager import InsideBarConfigManager


@pytest.fixture
def temp_repo(tmp_path):
    """Fixture to create a temporary strategy config repository."""
    config_dir = tmp_path / "configs" / "strategies"
    config_dir.mkdir(parents=True)
    
    # Write initial valid config (New Schema)
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
        
    return StrategyConfigRepository(base_path=config_dir)


def test_load_and_get_v1_ok(temp_repo):
    """Test loading a valid v1 configuration."""
    manager = InsideBarConfigManager(repository=temp_repo)
    config = manager.get("1.0.0")
    
    assert config["required_warmup_bars"] == 200
    assert config["core"]["atr_period"] == 14
    assert config["tunable"]["lookback_candles"] == 50


def test_get_metadata_ok(temp_repo):
    """Test get_metadata returns correct strategy info."""
    manager = InsideBarConfigManager(repository=temp_repo)
    meta = manager.get_metadata()
    
    assert meta["strategy_id"] == "insidebar_intraday"
    assert "1.0.0" in meta["versions"]


def test_strategy_id_mismatch_raises(temp_repo, tmp_path):
    """Test error when strategy_id in YAML does not match manager's strategy_id."""
    config_dir = tmp_path / "configs" / "strategies"
    yaml_file = config_dir / "insidebar_intraday.yaml"
    
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    content["strategy_id"] = "wrong_id"
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
        
    manager = InsideBarConfigManager(repository=temp_repo)
    with pytest.raises(ValueError, match="Strategy ID mismatch: expected 'insidebar_intraday', found 'wrong_id'"):
        manager.get("1.0.0")


def test_missing_core_key_raises(temp_repo, tmp_path):
    """Test validation failure when a required core key is missing."""
    config_dir = tmp_path / "configs" / "strategies"
    yaml_file = config_dir / "insidebar_intraday.yaml"
    
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    del content["versions"]["1.0.0"]["core"]["atr_period"]
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
        
    manager = InsideBarConfigManager(repository=temp_repo)
    with pytest.raises(ValueError, match="missing core key: atr_period"):
        manager.get("1.0.0")


def test_unknown_version_key_raises(temp_repo, tmp_path):
    """Test validation failure on unknown keys at the version level."""
    config_dir = tmp_path / "configs" / "strategies"
    yaml_file = config_dir / "insidebar_intraday.yaml"
    
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    content["versions"]["1.0.0"]["unknown_key"] = "surprise"
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
        
    manager = InsideBarConfigManager(repository=temp_repo)
    with pytest.raises(ValueError, match="unknown keys: unknown_key"):
        manager.get("1.0.0")


def test_unknown_core_key_raises(temp_repo, tmp_path):
    """Test validation failure on unknown keys within the core block."""
    config_dir = tmp_path / "configs" / "strategies"
    yaml_file = config_dir / "insidebar_intraday.yaml"
    
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    content["versions"]["1.0.0"]["core"]["extra_key"] = 123
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
        
    manager = InsideBarConfigManager(repository=temp_repo)
    with pytest.raises(ValueError, match="unknown core key: extra_key"):
        manager.get("1.0.0")


def test_unknown_tunable_key_raises(temp_repo, tmp_path):
    """Test validation failure on unknown keys within the tunable block."""
    config_dir = tmp_path / "configs" / "strategies"
    yaml_file = config_dir / "insidebar_intraday.yaml"
    
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    content["versions"]["1.0.0"]["tunable"]["mystery_key"] = True
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
        
    manager = InsideBarConfigManager(repository=temp_repo)
    with pytest.raises(ValueError, match="unknown tunable key: mystery_key"):
        manager.get("1.0.0")


def test_invalid_enum_raises(temp_repo, tmp_path):
    """Test validation failure on invalid enum values."""
    config_dir = tmp_path / "configs" / "strategies"
    yaml_file = config_dir / "insidebar_intraday.yaml"
    
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    content["versions"]["1.0.0"]["core"]["inside_bar_mode"] = "invalid_mode"
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
        
    manager = InsideBarConfigManager(repository=temp_repo)
    with pytest.raises(ValueError, match="invalid inside_bar_mode: invalid_mode"):
        manager.get("1.0.0")


def test_required_warmup_bars_type_and_range(temp_repo, tmp_path):
    """Test validation of required_warmup_bars (type and range)."""
    config_dir = tmp_path / "configs" / "strategies"
    yaml_file = config_dir / "insidebar_intraday.yaml"
    
    manager = InsideBarConfigManager(repository=temp_repo)
    
    # 1. Negative
    with open(yaml_file, 'r') as f:
        content = yaml.safe_load(f)
    content["versions"]["1.0.0"]["required_warmup_bars"] = -1
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
    with pytest.raises(ValueError, match="must be int >= 0"):
        manager.get("1.0.0")
        
    # 2. String
    content["versions"]["1.0.0"]["required_warmup_bars"] = "200"
    with open(yaml_file, 'w') as f:
        yaml.dump(content, f)
    with pytest.raises(ValueError, match="must be int >= 0"):
        manager.get("1.0.0")


def test_missing_version_raises(temp_repo):
    """Test error when requesting a non-existent version."""
    manager = InsideBarConfigManager(repository=temp_repo)
    with pytest.raises(ValueError, match="Version '9.9.9' not found"):
        manager.get("9.9.9")
