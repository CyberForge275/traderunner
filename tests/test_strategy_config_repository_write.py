"""Tests for StrategyConfigRepository write operations."""

import pytest
import yaml
from pathlib import Path
from src.strategies.config.repository import StrategyConfigRepository


@pytest.fixture
def temp_repo(tmp_path):
    """Fixture for temporary repository."""
    config_dir = tmp_path / "configs" / "strategies"
    config_dir.mkdir(parents=True)
    return StrategyConfigRepository(base_path=config_dir), config_dir


def test_write_strategy_file_atomic(temp_repo):
    """Test atomic write creates valid YAML file."""
    repo, config_dir = temp_repo
    
    content = {
        "strategy_id": "test_strategy",
        "canonical_name": "test",
        "versions": {
            "1.0.0": {
                "required_warmup_bars": 100,
                "core": {"param1": 10},
                "tunable": {"param2": 20}
            }
        }
    }
    
    repo.write_strategy_file("test_strategy", content)
    
    # Verify file exists
    yaml_file = config_dir / "test_strategy.yaml"
    assert yaml_file.exists()
    
    # Verify content is parseable and matches
    with open(yaml_file, 'r') as f:
        loaded = yaml.safe_load(f)
    
    assert loaded == content
    assert loaded["strategy_id"] == "test_strategy"
    assert "1.0.0" in loaded["versions"]


def test_write_rejects_strategy_id_mismatch(temp_repo):
    """Test write rejects when strategy_id doesn't match filename."""
    repo, _ = temp_repo
    
    content = {
        "strategy_id": "wrong_id",
        "versions": {"1.0.0": {"required_warmup_bars": 0, "core": {}}}
    }
    
    with pytest.raises(ValueError, match="Strategy ID mismatch"):
        repo.write_strategy_file("test_strategy", content)


def test_write_validates_yaml_structure(temp_repo):
    """Test write validates YAML can be parsed after write."""
    repo, config_dir = temp_repo
    
    # This should succeed (valid YAML)
    content = {
        "strategy_id": "test_strategy",
        "versions": {"1.0.0": {"required_warmup_bars": 0, "core": {}}}
    }
    
    repo.write_strategy_file("test_strategy", content)
    
    # Verify file is readable
    yaml_file = config_dir / "test_strategy.yaml"
    with open(yaml_file, 'r') as f:
        loaded = yaml.safe_load(f)
    assert loaded["strategy_id"] == "test_strategy"


def test_write_overwrites_existing_file(temp_repo):
    """Test write can overwrite existing file atomically."""
    repo, config_dir = temp_repo
    
    # Write v1
    content_v1 = {
        "strategy_id": "test_strategy",
        "versions": {"1.0.0": {"required_warmup_bars": 100, "core": {}}}
    }
    repo.write_strategy_file("test_strategy", content_v1)
    
    # Write v2 (with additional version)
    content_v2 = {
        "strategy_id": "test_strategy",
        "versions": {
            "1.0.0": {"required_warmup_bars": 100, "core": {}},
            "2.0.0": {"required_warmup_bars": 200, "core": {}}
        }
    }
    repo.write_strategy_file("test_strategy", content_v2)
    
    # Verify latest content
    yaml_file = config_dir / "test_strategy.yaml"
    with open(yaml_file, 'r') as f:
        loaded = yaml.safe_load(f)
    
    assert "2.0.0" in loaded["versions"]
    assert loaded["versions"]["2.0.0"]["required_warmup_bars"] == 200


def test_write_cleans_up_tmp_on_error(temp_repo, monkeypatch):
    """Test tmp file is cleaned up if write fails."""
    repo, config_dir = temp_repo
    
    content = {
        "strategy_id": "test_strategy",
        "versions": {"1.0.0": {"required_warmup_bars": 0, "core": {}}}
    }
    
    # Force a failure during YAML dump by making yaml.dump raise
    def bad_dump(*args, **kwargs):
        raise RuntimeError("Simulated write failure")
    
    monkeypatch.setattr(yaml, "dump", bad_dump)
    
    # Count tmp files before
    tmp_files_before = list(config_dir.glob(".test_strategy_*.yaml.tmp"))
    
    # Attempt write (should fail)
    with pytest.raises(RuntimeError, match="Simulated write failure"):
        repo.write_strategy_file("test_strategy", content)
    
    # Count tmp files after (should be same - cleaned up)
    tmp_files_after = list(config_dir.glob(".test_strategy_*.yaml.tmp"))
    assert len(tmp_files_after) == len(tmp_files_before)
