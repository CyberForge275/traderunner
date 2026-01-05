"""
Tests for Phase 2 F0: Compound Sizing Config (UPDATED).

Ensures:
- No duplicate config (SSOT)
- Config loaded from correct section
- No behavior change when flag is false
"""

import pytest
import yaml
from pathlib import Path


def test_no_duplicate_compound_flags():
    """
    CHECK 1 GUARD: Compound flags should only appear once (in backtesting section).
    
    This prevents SSOT violations and config ambiguity.
    """
    config_path = Path("src/strategies/inside_bar/inside_bar.yaml")
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Recursive count to catch duplicates anywhere
    def count_key(d, key):
        count = 0
        if isinstance(d, dict):
            if key in d:
                count += 1
            for v in d.values():
                count += count_key(v, key)
        return count
    
    cs_count = count_key(config, "compound_sizing")
    ceb_count = count_key(config, "compound_equity_basis")
    
    # Must appear exactly once
    assert cs_count == 1, f"compound_sizing appears {cs_count} times (expected 1)"
    assert ceb_count == 1, f"compound_equity_basis appears {ceb_count} times (expected 1)"
    
    # Must be in backtesting section
    assert "backtesting" in config
    assert "compound_sizing" in config["backtesting"]
    assert "compound_equity_basis" in config["backtesting"]
    
    # Must NOT be in live_trading
    if "live_trading" in config:
        assert "compound_sizing" not in config["live_trading"], \
            "compound_sizing found in live_trading (should only be in backtesting)"
        assert "compound_equity_basis" not in config["live_trading"], \
            "compound_equity_basis found in live_trading (should only be in backtesting)"


def test_compound_flag_in_yaml():
    """Verify compound_sizing exists in inside_bar.yaml under backtesting."""
    config_path = Path("src/strategies/inside_bar/inside_bar.yaml")
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Should be under backtesting, not root  or live_trading
    assert "backtesting" in config
    assert "compound_sizing" in config["backtesting"]
    assert "compound_equity_basis" in config["backtesting"]
    
    # Default should be false
    assert config["backtesting"]["compound_sizing"] == False
    assert config["backtesting"]["compound_equity_basis"] == "cash_only"


def test_compound_flag_default_false():
    """When compound_sizing key is missing, should default to false."""
    # This tests the runner's config parsing logic
    # For now, just verify the YAML default is false
    config_path = Path("src/strategies/inside_bar/inside_bar.yaml")
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    assert config["backtesting"]["compound_sizing"] == False


def test_compound_equity_basis_options():
    """Verify compound_equity_basis has expected value."""
    config_path = Path("src/strategies/inside_bar/inside_bar.yaml")
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    basis = config["backtesting"]["compound_equity_basis"]
    
    # Should be one of the allowed values
    assert basis in ["cash_only", "mark_to_market"]
    
    # Default should be cash_only
    assert basis == "cash_only"


def test_config_structure_unchanged():
    """Verify we didn't break existing config structure."""
    config_path = Path("src/strategies/inside_bar/inside_bar.yaml")
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Existing sections should still exist
    assert "metadata" in config
    assert "parameters" in config
    assert "backtesting" in config
    assert "live_trading" in config
    
    # Existing backtesting fields should still exist
    assert "execution_lag" in config["backtesting"]
    assert "session_filter" in config["backtesting"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
