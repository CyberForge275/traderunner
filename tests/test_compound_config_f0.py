"""Phase F0 compound config tests (SSOT-aligned, YAML-agnostic)."""

from pathlib import Path

import pytest

from axiom_bt.compound_config import CompoundConfig


def test_ssot_location_no_legacy_duplicates():
    """SSOT guard: legacy inside_bar YAML should be absent; new SSOT present."""
    legacy_path = Path("src/strategies/inside_bar/inside_bar.yaml")
    assert not legacy_path.exists(), "Legacy inside_bar.yaml should not be restored"

    ssot_path = Path("src/strategies/inside_bar/insidebar_intraday.yaml")
    assert ssot_path.exists(), "SSOT insidebar config must exist at configs/strategies"


def test_compound_flag_default_false():
    """CompoundConfig defaults to disabled/cash_only when keys are missing."""
    cfg = CompoundConfig.from_strategy_params({})
    assert cfg.enabled is False
    assert cfg.equity_basis == "cash_only"


def test_compound_flag_enabled_cash_only():
    """CompoundConfig reads flags from backtesting block."""
    params = {
        "backtesting": {
            "compound_sizing": True,
            "compound_equity_basis": "cash_only",
        }
    }
    cfg = CompoundConfig.from_strategy_params(params)
    assert cfg.enabled is True
    assert cfg.equity_basis == "cash_only"


def test_compound_equity_basis_options():
    """Only cash_only is accepted when enabled; mark_to_market raises."""
    cfg = CompoundConfig(enabled=True, equity_basis="cash_only")
    cfg.validate()  # should not raise

    cfg_bad = CompoundConfig(enabled=True, equity_basis="mark_to_market")
    with pytest.raises(NotImplementedError):
        cfg_bad.validate()


def test_config_export_shape():
    """to_dict exports stable manifest fields."""
    cfg = CompoundConfig(enabled=True, equity_basis="cash_only")
    assert cfg.to_dict() == {
        "compound_sizing": True,
        "compound_equity_basis": "cash_only",
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
