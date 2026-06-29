from strategies.registry import get_strategy
from src.strategies.config.registry import config_manager_registry
from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore


def test_strategy_discovery_includes_confirmed_breakout():
    plugin = get_strategy("confirmed_breakout_intraday")
    assert plugin.strategy_id == "confirmed_breakout_intraday"


def test_config_registry_includes_confirmed_breakout():
    # Import side-effect registers all known config managers for dashboard discovery.
    assert StrategyConfigStore is not None
    strategies = config_manager_registry.list_strategies()
    assert "confirmed_breakout_intraday" in strategies


def test_strategy_discovery_includes_harami_break():
    plugin = get_strategy("harami_break_intraday")
    assert plugin.strategy_id == "harami_break_intraday"


def test_strategy_discovery_includes_ndx_momentum_rotation():
    plugin = get_strategy("ndx_momentum_rotation")
    assert plugin.strategy_id == "ndx_momentum_rotation"


def test_config_registry_keeps_existing_and_adds_ndx():
    strategies = set(config_manager_registry.list_strategies())
    assert "insidebar_intraday" in strategies
    assert "confirmed_breakout_intraday" in strategies
    assert "harami_break_intraday" in strategies
    assert "ndx_momentum_rotation" in strategies


def test_strategy_discovery_includes_perlentaucher_daily_scan():
    plugin = get_strategy("perlentaucher_daily_scan")
    assert plugin.strategy_id == "perlentaucher_daily_scan"


def test_config_registry_includes_perlentaucher_daily_scan():
    strategies = set(config_manager_registry.list_strategies())
    assert "perlentaucher_daily_scan" in strategies
