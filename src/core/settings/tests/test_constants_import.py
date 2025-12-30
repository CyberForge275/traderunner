"""Test that all constants are properly importable from core.settings package."""
import pytest


def test_import_default_constants():
    """Verify default constants can be imported from core.settings."""
    from src.core.settings import (
        DEFAULT_INITIAL_CASH,
        DEFAULT_RISK_PCT,
        DEFAULT_MIN_QTY,
        DEFAULT_FEE_BPS,
        DEFAULT_SLIPPAGE_BPS,
    )

    # Verify values match expected defaults
    assert DEFAULT_INITIAL_CASH == 10_000.0
    assert DEFAULT_RISK_PCT == 1.0
    assert DEFAULT_MIN_QTY == 1
    assert DEFAULT_FEE_BPS == 2.0
    assert DEFAULT_SLIPPAGE_BPS == 1.0


def test_import_inside_bar_constants():
    """Verify InsideBar-specific constants can be imported."""
    from src.core.settings import (
        INSIDE_BAR_TIMEZONE,
        INSIDE_BAR_SESSIONS,
        INSIDE_BAR_DEFAULT_DATA_TZ,
    )

    assert INSIDE_BAR_TIMEZONE == "Europe/Berlin"
    assert INSIDE_BAR_SESSIONS == ["15:00-16:00", "16:00-17:00"]
    assert INSIDE_BAR_DEFAULT_DATA_TZ == "Europe/Berlin"


def test_import_strategy_defaults():
    """Verify StrategyDefaults dataclass and instance can be imported."""
    from src.core.settings import StrategyDefaults, INSIDE_BAR_DEFAULTS

    # Check dataclass is available
    assert StrategyDefaults is not None

    # Check instance has correct structure
    assert INSIDE_BAR_DEFAULTS.name == "insidebar_intraday"
    assert INSIDE_BAR_DEFAULTS.timezone == "Europe/Berlin"
    assert INSIDE_BAR_DEFAULTS.initial_cash == 10_000.0
    assert INSIDE_BAR_DEFAULTS.risk_pct == 1.0
    assert "fees_bps" in INSIDE_BAR_DEFAULTS.costs
    assert "slippage_bps" in INSIDE_BAR_DEFAULTS.costs


def test_all_exports_in__all__():
    """Verify __all__ contains all expected exports."""
    from src.core import settings

    expected_exports = [
        "TradingSettings",
        "get_settings",
        "DEFAULT_INITIAL_CASH",
        "DEFAULT_RISK_PCT",
        "DEFAULT_MIN_QTY",
        "DEFAULT_FEE_BPS",
        "DEFAULT_SLIPPAGE_BPS",
        "INSIDE_BAR_TIMEZONE",
        "INSIDE_BAR_SESSIONS",
        "INSIDE_BAR_DEFAULT_DATA_TZ",
        "StrategyDefaults",
        "INSIDE_BAR_DEFAULTS",
    ]

    for export in expected_exports:
        assert export in settings.__all__, f"{export} not in __all__"
        assert hasattr(settings, export), f"{export} not accessible from module"


def test_backward_compatibility():
    """Verify existing imports still work (backward compatibility)."""
    # This is how axiom_bt/runner.py imports it
    from src.core.settings import DEFAULT_INITIAL_CASH

    # This is how apps/streamlit/app.py imports it
    from src.core.settings import DEFAULT_INITIAL_CASH, INSIDE_BAR_TIMEZONE

    # Verify they have correct values
    assert DEFAULT_INITIAL_CASH == 10_000.0
    assert INSIDE_BAR_TIMEZONE == "Europe/Berlin"
