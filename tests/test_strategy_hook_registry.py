import pandas as pd

from axiom_bt.strategy_hooks.registry import get_hook, list_strategies


def test_registry_lists_insidebar():
    strategies = list_strategies()
    assert "insidebar_intraday" in strategies


def test_registry_resolves_insidebar_and_builds():
    hook = get_hook("insidebar_intraday")
    bars = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=3, freq="5min", tz="UTC"),
            "open": [1, 2, 3],
            "high": [1.1, 2.1, 3.1],
            "low": [0.9, 1.9, 2.9],
            "close": [1.05, 2.05, 3.05],
            "volume": [10, 10, 10],
        }
    )
    df = hook.extend_signal_frame(bars, {"symbol": "T", "timeframe": "M5", "strategy_version": "1.0.0"})
    assert not df.empty
    assert (df["strategy_id"] == "insidebar_intraday").all()
