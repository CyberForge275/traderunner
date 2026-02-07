import pandas as pd

from trading_dashboard.components.row_inspector import resolve_trade_oco_levels
from trading_dashboard.components.signal_chart import compute_trade_chart_window


def test_compute_trade_chart_window_end_is_exit_plus_5_bars():
    ts = pd.date_range("2025-01-01 14:00:00+00:00", periods=30, freq="5min")
    bars = pd.DataFrame(
        {
            "timestamp": ts,
            "open": range(30),
            "high": range(30),
            "low": range(30),
            "close": range(30),
        }
    )
    anchor_ts = ts[10]
    exit_ts = ts[15]
    window, meta = compute_trade_chart_window(bars, anchor_ts, exit_ts, pre_bars=10, post_bars=5)

    assert not window.empty
    assert meta["exit_idx"] == 15
    assert meta["end_idx"] == 20


def test_resolve_trade_oco_levels_uses_signal_ts_only():
    orders_rows = [
        {
            "template_id": "t1",
            "oco_group_id": "g1",
            "signal_ts": "2025-05-13 14:40:00+00:00",
            "dbg_inside_ts": "2025-05-13 14:35:00+00:00",
            "side": "BUY",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "take_profit_price": 101.0,
        },
        {
            "template_id": "t1_s",
            "oco_group_id": "g1",
            "signal_ts": "2025-05-13 14:40:00+00:00",
            "dbg_inside_ts": "2025-05-13 14:35:00+00:00",
            "side": "SELL",
            "entry_price": 98.0,
            "stop_price": 99.5,
            "take_profit_price": 97.0,
        },
    ]
    trade_row = {"template_id": "t1"}
    resolved = resolve_trade_oco_levels(trade_row, orders_rows)
    assert resolved["signal_ts"] == pd.Timestamp("2025-05-13 14:40:00+00:00")
    assert resolved["levels"]["long"]["entry"] == 100.0
    assert resolved["levels"]["short"]["entry"] == 98.0


def test_resolve_trade_oco_levels_missing_signal_ts_returns_none():
    orders_rows = [
        {"template_id": "t1", "oco_group_id": "g1", "side": "BUY", "entry_price": 100.0},
        {"template_id": "t1_s", "oco_group_id": "g1", "side": "SELL", "entry_price": 98.0},
    ]
    trade_row = {"template_id": "t1"}
    resolved = resolve_trade_oco_levels(trade_row, orders_rows)
    assert resolved["signal_ts"] is None
