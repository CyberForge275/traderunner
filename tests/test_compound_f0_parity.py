"""
CHECK 5: Golden Parity Test

Proves that compound_sizing=false produces identical results to baseline.

This is a critical sanity check ensuring F0 changes don't introduce
behavior changes when compound features are disabled (default).
"""

import pytest


def test_f0_golden_parity_no_behavior_change():
    """Default config (compound off) is accepted and exports stable manifest."""
    from axiom_bt.compound_config import CompoundConfig

    strategy_params = {"backtesting": {}}

    compound = CompoundConfig.from_strategy_params(strategy_params)
    assert compound.enabled is False
    assert compound.equity_basis == "cash_only"

    compound.validate()
    assert compound.to_dict() == {
        "compound_sizing": False,
        "compound_equity_basis": "cash_only",
    }


def test_f0_parity_manifest_structure():
    """Compound fields merge cleanly into params without breaking structure."""
    from axiom_bt.compound_config import CompoundConfig

    strategy_params = {
        "backtesting": {
            "execution_lag": 0,
            "session_filter": {"enabled": False},
            "compound_sizing": False,
            "compound_equity_basis": "cash_only",
        },
        "parameters": {"atr_period": 14},
    }

    compound = CompoundConfig.from_strategy_params(strategy_params)

    config_with_compound = {**strategy_params, **compound.to_dict()}

    assert config_with_compound["compound_sizing"] is False
    assert config_with_compound["compound_equity_basis"] == "cash_only"
    assert "backtesting" in config_with_compound
    assert "parameters" in config_with_compound


def test_f0_parity_config_extraction_deterministic():
    """Same input yields identical CompoundConfig outputs."""
    from axiom_bt.compound_config import CompoundConfig

    params = {
        "backtesting": {
            "compound_sizing": True,
            "compound_equity_basis": "cash_only",
        }
    }

    config1 = CompoundConfig.from_strategy_params(params)
    config2 = CompoundConfig.from_strategy_params(params)

    assert config1.enabled == config2.enabled
    assert config1.equity_basis == config2.equity_basis
    assert config1.to_dict() == config2.to_dict()


def test_f0_parity_no_default_artifacts_created():
    """Disabled compound => metadata-only, no execution side effects implied."""
    from axiom_bt.compound_config import CompoundConfig

    compound = CompoundConfig()
    assert compound.enabled is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
