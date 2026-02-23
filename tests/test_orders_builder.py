from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))

import trade.orders_builder as orders_builder


def test_build_orders_for_backtest_emits_deprecation_warning(monkeypatch):
    def fake_build(signals, ts_col, sessions, args):  # type: ignore[override]
        return pd.DataFrame()

    monkeypatch.setattr(orders_builder, "_build_inside_bar_orders", fake_build)
    df = pd.DataFrame([{"timestamp": "2025-10-06T15:30:00Z"}])
    with pytest.warns(DeprecationWarning, match="deprecated"):
        orders_builder.build_orders_for_backtest(
            df,
            strategy_params={"max_position_loss_pct_equity": None},
        )


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

    params: dict = {"max_position_loss_pct_equity": None}
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

    result = orders_builder.build_orders_for_backtest(
        df,
        strategy_params={"max_position_loss_pct_equity": None},
    )
    assert isinstance(result, pd.DataFrame)
    assert calls["ts_col"] == "ts"


def test_build_orders_for_backtest_empty_signals_returns_empty_df(monkeypatch):
    # Ensure empty signal frame does not crash and returns an empty orders DataFrame
    def fake_build(signals, ts_col, sessions, args):  # type: ignore[override]
        assert signals.empty
        return pd.DataFrame()

    monkeypatch.setattr(orders_builder, "_build_inside_bar_orders", fake_build)

    df = pd.DataFrame(columns=["timestamp", "Symbol", "long_entry", "sl_long", "tp_long"])
    result = orders_builder.build_orders_for_backtest(
        df,
        strategy_params={"max_position_loss_pct_equity": None},
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_build_orders_requires_explicit_max_position_loss_pct_equity(monkeypatch):
    def fake_build(signals, ts_col, sessions, args):  # type: ignore[override]
        return pd.DataFrame()

    monkeypatch.setattr(orders_builder, "_build_inside_bar_orders", fake_build)
    df = pd.DataFrame(columns=["timestamp", "Symbol", "long_entry", "sl_long", "tp_long"])

    try:
        orders_builder.build_orders_for_backtest(df, strategy_params={})
    except ValueError as exc:
        assert "max_position_loss_pct_equity" in str(exc)
    else:
        raise AssertionError("expected ValueError when max_position_loss_pct_equity is missing")


def test_risk_cap_reduces_qty_from_max_position_loss_pct_equity(monkeypatch):
    def fake_build(signals, ts_col, sessions, args):  # type: ignore[override]
        return pd.DataFrame(
            [
                {
                    "valid_from": "2025-01-01T15:00:00Z",
                    "valid_to": "2025-01-01T21:00:00Z",
                    "entry_price": 100.0,
                    "stop_price": 98.0,
                    "qty": 1000,
                }
            ]
        )

    monkeypatch.setattr(orders_builder, "_build_inside_bar_orders", fake_build)
    out = orders_builder.build_orders_for_backtest(
        signals=pd.DataFrame([{"timestamp": "2025-01-01T15:00:00Z"}]),
        strategy_params={
            "order_validity_policy": "session_end",
            "session_filter": ["09:30-16:00"],
            "session_timezone": "America/New_York",
            "valid_from_policy": "signal_ts",
            "timeframe_minutes": 5,
            "max_position_loss_pct_equity": 0.01,
            "initial_cash": 100000,
        },
    )
    assert int(out.iloc[0]["qty"]) == 500


def test_risk_cap_qty_zero_rejects_order(monkeypatch):
    def fake_build(signals, ts_col, sessions, args):  # type: ignore[override]
        return pd.DataFrame(
            [
                {
                    "valid_from": "2025-01-01T15:00:00Z",
                    "valid_to": "2025-01-01T21:00:00Z",
                    "entry_price": 100.0,
                    "stop_price": 80.0,
                    "qty": 10,
                }
            ]
        )

    monkeypatch.setattr(orders_builder, "_build_inside_bar_orders", fake_build)
    out = orders_builder.build_orders_for_backtest(
        signals=pd.DataFrame([{"timestamp": "2025-01-01T15:00:00Z"}]),
        strategy_params={
            "order_validity_policy": "session_end",
            "session_filter": ["09:30-16:00"],
            "session_timezone": "America/New_York",
            "valid_from_policy": "signal_ts",
            "timeframe_minutes": 5,
            "max_position_loss_pct_equity": 0.0001,
            "initial_cash": 100000,
        },
    )
    assert out.empty
