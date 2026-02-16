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


def _run_exec_with_two_trades(commission_bps: float, slippage_bps: float):
    t0 = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")
    t1 = pd.Timestamp("2025-04-03 14:40:00", tz="UTC")
    t2 = pd.Timestamp("2025-04-03 14:45:00", tz="UTC")
    t3 = pd.Timestamp("2025-04-03 14:50:00", tz="UTC")
    bars = _bars([t0, t1, t2, t3], [100.0, 101.0, 102.0, 103.0], [101.0, 102.0, 103.0, 104.0], [99.0, 100.0, 101.0, 102.0])

    fills = pd.DataFrame(
        [
            {"template_id": "buy1", "symbol": "HOOD", "fill_ts": t0, "fill_price": 100.0, "reason": "signal_fill"},
            {"template_id": "buy1", "symbol": "HOOD", "fill_ts": t1, "fill_price": 104.0, "reason": "take_profit"},
            {"template_id": "sell1", "symbol": "HOOD", "fill_ts": t2, "fill_price": 103.0, "reason": "signal_fill"},
            {"template_id": "sell1", "symbol": "HOOD", "fill_ts": t3, "fill_price": 101.0, "reason": "take_profit"},
        ]
    )
    intents = pd.DataFrame(
        [
            {"template_id": "buy1", "side": "BUY"},
            {"template_id": "sell1", "side": "SELL"},
        ]
    )

    return execute(
        fills,
        intents,
        bars,
        initial_cash=1000.0,
        compound_enabled=False,
        order_validity_policy="session_end",
        session_timezone="America/New_York",
        session_filter=["09:30-11:00", "14:00-15:00"],
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


def test_fills_csv_has_audit_columns_when_costs_enabled():
    exec_art = _run_exec_with_two_trades(commission_bps=2.0, slippage_bps=1.0)
    fills = exec_art.fills
    expected = {
        "fill_price_ideal",
        "fill_price_exec",
        "commission_cost",
        "slippage_cost",
        "total_cost",
        "effective_commission_bps",
        "effective_slippage_bps",
        "price_semantics",
        "fill_side",
        "fill_qty",
    }
    assert expected.issubset(set(fills.columns))


def test_fill_costs_aggregate_to_trade_costs():
    exec_art = _run_exec_with_two_trades(commission_bps=2.0, slippage_bps=1.0)
    fills = exec_art.fills
    trades = exec_art.trades

    assert fills["total_cost"].sum() == pytest.approx(trades["total_cost"].sum())
    assert fills["commission_cost"].sum() == pytest.approx(trades["commission_cost"].sum())
    assert fills["slippage_cost"].sum() == pytest.approx(trades["slippage_cost"].sum())


def test_fill_exec_price_direction_is_worse_for_buy_sell():
    exec_art = _run_exec_with_two_trades(commission_bps=2.0, slippage_bps=1.0)
    fills = exec_art.fills

    buy_fills = fills[fills["fill_side"] == "BUY"]
    sell_fills = fills[fills["fill_side"] == "SELL"]
    assert not buy_fills.empty
    assert not sell_fills.empty
    assert (buy_fills["fill_price_exec"] >= buy_fills["fill_price_ideal"]).all()
    assert (sell_fills["fill_price_exec"] <= sell_fills["fill_price_ideal"]).all()


def test_zero_costs_fill_fields_present_but_zero():
    exec_art = _run_exec_with_two_trades(commission_bps=0.0, slippage_bps=0.0)
    fills = exec_art.fills
    assert (fills["commission_cost"] == 0.0).all()
    assert (fills["slippage_cost"] == 0.0).all()
    assert (fills["total_cost"] == 0.0).all()
