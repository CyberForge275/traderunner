# tests/architecture/test_strategy_catalog_consistency.py

from typing import Set

from apps.streamlit.state import STRATEGY_REGISTRY
from trading_dashboard.utils.strategy_helpers import get_available_strategies
from trading_dashboard.layouts.pre_papertrade import _get_strategy_options


def _catalog_ids() -> Set[str]:
    """Return all strategy IDs from the central Strategy Registry."""
    return set(STRATEGY_REGISTRY.keys())


def _ui_strategy_ids_backtests() -> Set[str]:
    """
    Strategy IDs used in general dashboard selection
    (e.g. Backtests / generic strategy selector).
    """
    return set(get_available_strategies())


def _ui_strategy_ids_pre_papertrade() -> Set[str]:
    """
    Strategy IDs used in the Pre-PaperTrade strategy dropdown.

    We only care about the 'value' of each option.
    """
    options = _get_strategy_options()
    values = {opt["value"] for opt in options if "value" in opt}
    return values


def test_backtests_ui_strategies_exist_in_catalog():
    """All UI strategies for Backtests must have entries in STRATEGY_REGISTRY."""
    catalog = _catalog_ids()
    ui_ids = _ui_strategy_ids_backtests()

    missing = sorted(ui_ids - catalog)
    assert not missing, (
        "Dashboard strategies without STRATEGY_REGISTRY entry: "
        f"{missing}"
    )


def test_pre_papertrade_ui_strategies_exist_in_catalog():
    """All Pre-PaperTrade strategy options must exist in STRATEGY_REGISTRY."""
    catalog = _catalog_ids()
    ui_ids = _ui_strategy_ids_pre_papertrade()

    missing = sorted(ui_ids - catalog)
    assert not missing, (
        "Pre-PaperTrade strategies without STRATEGY_REGISTRY entry: "
        f"{missing}"
    )
