import pandas as pd
import pytest

from axiom_bt.pipeline.execution import execute


def _bars(ts_list, closes, highs, lows):
    return pd.DataFrame(
        {
            "timestamp": ts_list,
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1.0] * len(ts_list),
        }
    )


def test_execution_builds_one_trade_per_template_id_from_fills():
    t0 = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")
    t1 = pd.Timestamp("2025-04-03 14:40:00", tz="UTC")
    bars = _bars([t0, t1], [100.0, 101.0], [101.0, 102.0], [99.0, 100.0])

    fills = pd.DataFrame(
        [
            {"template_id": "t1", "symbol": "HOOD", "fill_ts": t0, "fill_price": 100.0, "reason": "signal_fill"},
            {"template_id": "t1", "symbol": "HOOD", "fill_ts": t1, "fill_price": 104.0, "reason": "take_profit"},
        ]
    )
    intents = pd.DataFrame(
        [
            {"template_id": "t1", "side": "BUY"},
        ]
    )

    exec_art = execute(
        fills,
        intents,
        bars,
        initial_cash=1000.0,
        compound_enabled=False,
        order_validity_policy="session_end",
        session_timezone="America/New_York",
        session_filter=["09:30-11:00", "14:00-15:00"],
    )

    trades = exec_art.trades
    assert len(trades) == 1
    assert trades.loc[0, "template_id"] == "t1"
    assert pd.to_datetime(trades.loc[0, "entry_ts"], utc=True) == t0
    assert pd.to_datetime(trades.loc[0, "exit_ts"], utc=True) == t1
    assert trades.loc[0, "reason"] == "take_profit"


def test_execution_uses_exit_fill_reason_over_intent_fallback():
    t0 = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")
    t1 = pd.Timestamp("2025-04-03 14:40:00", tz="UTC")
    t2 = pd.Timestamp("2025-04-03 19:00:00", tz="UTC")
    bars = _bars([t0, t1, t2], [100.0, 101.0, 102.0], [101.0, 102.0, 103.0], [99.0, 100.0, 101.0])

    fills = pd.DataFrame(
        [
            {"template_id": "t1", "symbol": "HOOD", "fill_ts": t0, "fill_price": 100.0, "reason": "signal_fill"},
            {"template_id": "t1", "symbol": "HOOD", "fill_ts": t1, "fill_price": 104.0, "reason": "take_profit"},
        ]
    )
    intents = pd.DataFrame(
        [
            {"template_id": "t1", "side": "BUY", "order_valid_to_ts": t2, "order_valid_to_reason": "session_end"},
        ]
    )

    exec_art = execute(
        fills,
        intents,
        bars,
        initial_cash=1000.0,
        compound_enabled=False,
        order_validity_policy="session_end",
        session_timezone="America/New_York",
        session_filter=["09:30-11:00", "14:00-15:00"],
    )

    trades = exec_art.trades
    assert len(trades) == 1
    assert trades.loc[0, "reason"] == "take_profit"
    assert pd.to_datetime(trades.loc[0, "exit_ts"], utc=True) == t1


def test_execution_applies_slippage_and_commission_to_net_pnl():
    t0 = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")
    t1 = pd.Timestamp("2025-04-03 14:40:00", tz="UTC")
    bars = _bars([t0, t1], [100.0, 101.0], [101.0, 102.0], [99.0, 100.0])

    fills = pd.DataFrame(
        [
            {"template_id": "t1", "symbol": "HOOD", "fill_ts": t0, "fill_price": 100.0, "reason": "signal_fill"},
            {"template_id": "t1", "symbol": "HOOD", "fill_ts": t1, "fill_price": 104.0, "reason": "take_profit"},
        ]
    )
    intents = pd.DataFrame([{"template_id": "t1", "side": "BUY"}])

    exec_art = execute(
        fills,
        intents,
        bars,
        initial_cash=1000.0,
        compound_enabled=False,
        order_validity_policy="session_end",
        session_timezone="America/New_York",
        session_filter=["09:30-11:00", "14:00-15:00"],
        commission_bps=100.0,
        slippage_bps=100.0,
    )

    trade = exec_art.trades.iloc[0]
    assert trade["gross_pnl"] == pytest.approx(4.0)
    assert trade["entry_exec_price"] == pytest.approx(101.0)
    assert trade["exit_exec_price"] == pytest.approx(102.96)
    assert trade["slippage_cost"] == pytest.approx(2.04)
    assert trade["commission_cost"] == pytest.approx(2.0396)
    assert trade["total_cost"] == pytest.approx(4.0796)
    assert trade["net_pnl"] == trade["pnl"]
    assert trade["net_pnl"] == pytest.approx(-0.0796)
