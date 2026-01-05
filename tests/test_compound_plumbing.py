"""
Tests for CHECK 2-4: Compound config plumbing, manifest, and guards.
"""

import pytest
import yaml
from pathlib import Path

from axiom_bt.compound_config import CompoundConfig


def test_compound_config_from_strategy_params_defaults():
    """CHECK 2: CompoundConfig extracts defaults when keys missing."""
    params = {"some_other_key": 123}
    
    config = CompoundConfig.from_strategy_params(params)
    
    assert config.enabled == False
    assert config.equity_basis == "cash_only"


def test_compound_config_from_strategy_params_backtesting_section():
    """CHECK 2: CompoundConfig reads from backtesting section (SSOT)."""
    params = {
        "backtesting": {
            "compound_sizing": True,
            "compound_equity_basis": "cash_only"
        }
    }
    
    config = CompoundConfig.from_strategy_params(params)
    
    assert config.enabled == True
    assert config.equity_basis == "cash_only"


def test_compound_config_validate_success():
    """CHECK 4: Validation passes for valid config."""
    config = CompoundConfig(enabled=True, equity_basis="cash_only")
    
    # Should not raise
    config.validate()


def test_compound_config_validate_mark_to_market_rejected():
    """CHECK 4: mark_to_market raises NotImplementedError when compound enabled."""
    config = CompoundConfig(enabled=True, equity_basis="mark_to_market")
    
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        config.validate()


def test_compound_config_validate_mark_to_market_ignored_when_disabled():
    """CHECK 4: mark_to_market does NOT raise when compound disabled."""
    config = CompoundConfig(enabled=False, equity_basis="mark_to_market")
    
    # Should not raise - compound is disabled so equity_basis is ignored
    config.validate()


def test_compound_config_validate_invalid_equity_basis():
    """CHECK 4: Invalid equity_basis raises ValueError."""
    config = CompoundConfig(enabled=True, equity_basis="invalid_value")
    
    with pytest.raises(ValueError, match="Invalid compound_equity_basis"):
        config.validate()


def test_compound_config_to_dict():
    """CHECK 3: to_dict() exports for manifest."""
    config = CompoundConfig(enabled=True, equity_basis="cash_only")
    
    result = config.to_dict()
    
    assert result == {
        "compound_sizing": True,
        "compound_equity_basis": "cash_only"
    }


def test_compound_flags_are_wired_to_yaml():
    """CHECK 2: Verify YAML contains compound flags in correct location."""
    config_path = Path("src/strategies/inside_bar/inside_bar.yaml")
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Must be in backtesting section
    assert "backtesting" in config
    bt = config["backtesting"]
    
    assert "compound_sizing" in bt
    assert "compound_equity_basis" in bt
    
    # Verify defaults
    assert bt["compound_sizing"] == False
    assert bt["compound_equity_basis"] == "cash_only"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
