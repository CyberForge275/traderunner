from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))

import trade.orders_builder as orders_builder


def test_build_orders_for_backtest_uses_timestamp_and_market_tz(monkeypatch):
    calls: dict = {}

    def fake_build(signals, ts_col, sessions, args):  # type: ignore[override]
        calls["signals"] = signals
        calls["ts_col"] = ts_col
        calls["sessions"] = sessions
        calls["args"] = args
        return pd.DataFrame()

    monkeypatch.setattr(orders_builder, "_build_inside_bar_orders", fake_build)

    df = pd.DataFrame(
        [
            {
                "timestamp": "2025-10-06T15:30:00Z",
                "Symbol": "APP",
                "long_entry": 10.0,
                "sl_long": 9.5,
                "tp_long": 11.0,
            }
        ]
    )

    params: dict = {}
    result = orders_builder.build_orders_for_backtest(
        signals=df,
        strategy_params=params,
        market_tz="America/New_York",
    )

    assert isinstance(result, pd.DataFrame)
    assert calls["ts_col"] == "timestamp"
    # tz must be passed through to the builder
    assert getattr(calls["args"], "tz") == "America/New_York"
    # default session should be a single window
    assert len(calls["sessions"]) == 1


def test_build_orders_for_backtest_uses_ts_when_no_timestamp(monkeypatch):
    calls: dict = {}

    def fake_build(signals, ts_col, sessions, args):  # type: ignore[override]
        calls["ts_col"] = ts_col
        return pd.DataFrame()

    monkeypatch.setattr(orders_builder, "_build_inside_bar_orders", fake_build)

    df = pd.DataFrame(
        [
            {
                "ts": "2025-10-06T15:30:00Z",
                "Symbol": "APP",
                "long_entry": 10.0,
                "sl_long": 9.5,
                "tp_long": 11.0,
            }
        ]
    )

    result = orders_builder.build_orders_for_backtest(df, strategy_params={})
    assert isinstance(result, pd.DataFrame)
    assert calls["ts_col"] == "ts"


def test_build_orders_for_backtest_empty_signals_returns_empty_df(monkeypatch):
    # Ensure empty signal frame does not crash and returns an empty orders DataFrame
    def fake_build(signals, ts_col, sessions, args):  # type: ignore[override]
        assert signals.empty
        return pd.DataFrame()

    monkeypatch.setattr(orders_builder, "_build_inside_bar_orders", fake_build)

    df = pd.DataFrame(columns=["timestamp", "Symbol", "long_entry", "sl_long", "tp_long"])
    result = orders_builder.build_orders_for_backtest(df, strategy_params={})

    assert isinstance(result, pd.DataFrame)
    assert result.empty
