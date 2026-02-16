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
