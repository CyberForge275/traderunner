import pandas as pd

from axiom_bt.pipeline.fill_model import generate_fills


def _bars(ts_list, opens, highs, lows, closes):
    return pd.DataFrame(
        {
            "timestamp": ts_list,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1.0] * len(ts_list),
        }
    )


def test_entry_fill_sell_crossing_uses_trigger_level():
    t0 = pd.Timestamp("2025-05-30 13:55:00", tz="UTC")
    t1 = pd.Timestamp("2025-05-30 14:00:00", tz="UTC")
    trigger = 63.42
    bars = _bars(
        [t0, t1],
        opens=[63.60, 63.50],
        highs=[63.70, 63.80],
        lows=[63.30, 63.40],
        closes=[63.05, 63.55],
    )
    intent = pd.DataFrame(
        [
            {
                "template_id": "ib_case",
                "signal_ts": t0,
                "symbol": "HOOD",
                "side": "SELL",
                "entry_price": trigger,
                "stop_price": 63.82,
                "take_profit_price": 62.62,
                "order_valid_to_ts": t1,
                "strategy_id": "insidebar_intraday",
            }
        ]
    )
    fills = generate_fills(intent, bars).fills
    entry = fills[fills["reason"] == "signal_fill"].iloc[0]
    assert float(entry["fill_price"]) == trigger


def test_entry_fill_sell_gap_uses_open():
    t0 = pd.Timestamp("2025-05-30 13:55:00", tz="UTC")
    t1 = pd.Timestamp("2025-05-30 14:00:00", tz="UTC")
    trigger = 63.42
    bars = _bars(
        [t0, t1],
        opens=[63.10, 63.20],
        highs=[63.50, 63.60],
        lows=[63.00, 63.10],
        closes=[63.15, 63.25],
    )
    intent = pd.DataFrame(
        [
            {
                "template_id": "ib_gap",
                "signal_ts": t0,
                "symbol": "HOOD",
                "side": "SELL",
                "entry_price": trigger,
                "stop_price": 63.82,
                "take_profit_price": 62.62,
                "order_valid_to_ts": t1,
                "strategy_id": "insidebar_intraday",
            }
        ]
    )
    fills = generate_fills(intent, bars).fills
    entry = fills[fills["reason"] == "signal_fill"].iloc[0]
    assert float(entry["fill_price"]) == 63.10


def test_entry_fill_buy_crossing_uses_trigger_level():
    t0 = pd.Timestamp("2025-05-30 13:55:00", tz="UTC")
    t1 = pd.Timestamp("2025-05-30 14:00:00", tz="UTC")
    trigger = 64.62
    bars = _bars(
        [t0, t1],
        opens=[64.40, 64.50],
        highs=[64.70, 64.80],
        lows=[64.30, 64.40],
        closes=[64.55, 64.60],
    )
    intent = pd.DataFrame(
        [
            {
                "template_id": "ib_buy",
                "signal_ts": t0,
                "symbol": "HOOD",
                "side": "BUY",
                "entry_price": trigger,
                "stop_price": 64.20,
                "take_profit_price": 65.20,
                "order_valid_to_ts": t1,
                "strategy_id": "insidebar_intraday",
            }
        ]
    )
    fills = generate_fills(intent, bars).fills
    entry = fills[fills["reason"] == "signal_fill"].iloc[0]
    assert float(entry["fill_price"]) == trigger


def test_entry_fill_buy_gap_uses_open():
    t0 = pd.Timestamp("2025-05-30 13:55:00", tz="UTC")
    t1 = pd.Timestamp("2025-05-30 14:00:00", tz="UTC")
    trigger = 64.62
    bars = _bars(
        [t0, t1],
        opens=[64.80, 64.90],
        highs=[65.00, 65.10],
        lows=[64.70, 64.80],
        closes=[64.85, 64.95],
    )
    intent = pd.DataFrame(
        [
            {
                "template_id": "ib_buy_gap",
                "signal_ts": t0,
                "symbol": "HOOD",
                "side": "BUY",
                "entry_price": trigger,
                "stop_price": 64.20,
                "take_profit_price": 65.20,
                "order_valid_to_ts": t1,
                "strategy_id": "insidebar_intraday",
            }
        ]
    )
    fills = generate_fills(intent, bars).fills
    entry = fills[fills["reason"] == "signal_fill"].iloc[0]
    assert float(entry["fill_price"]) == 64.80
