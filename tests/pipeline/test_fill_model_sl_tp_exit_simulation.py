import pandas as pd

from axiom_bt.pipeline.fill_model import generate_fills


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


def test_take_profit_triggers():
    t0 = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")
    t1 = pd.Timestamp("2025-04-03 14:40:00", tz="UTC")
    bars = _bars([t0, t1], [100.0, 101.0], [100.5, 105.0], [99.5, 100.5])
    intent = pd.DataFrame(
        [
            {
                "template_id": "t1",
                "signal_ts": t0,
                "symbol": "HOOD",
                "side": "BUY",
                "entry_price": 100.0,
                "stop_price": 98.0,
                "take_profit_price": 104.0,
            }
        ]
    )
    fills = generate_fills(intent, bars, order_validity_policy="session_end", session_timezone="America/New_York", session_filter=["09:30-11:00", "14:00-15:00"]).fills
    assert len(fills) == 2
    reasons = fills["reason"].tolist()
    assert "signal_fill" in reasons
    assert "take_profit" in reasons
    exit_row = fills[fills["reason"] == "take_profit"].iloc[0]
    assert float(exit_row["fill_price"]) == 104.0


def test_stop_loss_triggers():
    t0 = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")
    t1 = pd.Timestamp("2025-04-03 14:40:00", tz="UTC")
    bars = _bars([t0, t1], [100.0, 99.0], [100.5, 100.0], [99.5, 97.5])
    intent = pd.DataFrame(
        [
            {
                "template_id": "t1",
                "signal_ts": t0,
                "symbol": "HOOD",
                "side": "BUY",
                "entry_price": 100.0,
                "stop_price": 98.0,
                "take_profit_price": 104.0,
            }
        ]
    )
    fills = generate_fills(intent, bars, order_validity_policy="session_end", session_timezone="America/New_York", session_filter=["09:30-11:00", "14:00-15:00"]).fills
    assert len(fills) == 2
    exit_row = fills[fills["reason"] == "stop_loss"].iloc[0]
    assert float(exit_row["fill_price"]) == 98.0


def test_conflict_stop_wins():
    t0 = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")
    t1 = pd.Timestamp("2025-04-03 14:40:00", tz="UTC")
    bars = _bars([t0, t1], [100.0, 101.0], [105.0, 106.0], [97.0, 96.0])
    intent = pd.DataFrame(
        [
            {
                "template_id": "t1",
                "signal_ts": t0,
                "symbol": "HOOD",
                "side": "BUY",
                "entry_price": 100.0,
                "stop_price": 98.0,
                "take_profit_price": 104.0,
            }
        ]
    )
    fills = generate_fills(intent, bars, order_validity_policy="session_end", session_timezone="America/New_York", session_filter=["09:30-11:00", "14:00-15:00"]).fills
    exit_row = fills[fills["reason"] != "signal_fill"].iloc[0]
    assert exit_row["reason"] == "stop_loss"


def test_no_trigger_session_end():
    t0 = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")  # 10:35 NY
    t1 = pd.Timestamp("2025-04-03 19:00:00", tz="UTC")  # 15:00 NY
    bars = _bars([t0, t1], [100.0, 101.0], [100.5, 101.5], [99.5, 100.5])
    intent = pd.DataFrame(
        [
            {
                "template_id": "t1",
                "signal_ts": t0,
                "symbol": "HOOD",
                "side": "BUY",
                "entry_price": 100.0,
                "stop_price": 98.0,
                "take_profit_price": 104.0,
            }
        ]
    )
    fills = generate_fills(intent, bars, order_validity_policy="session_end", session_timezone="America/New_York", session_filter=["09:30-11:00", "14:00-15:00"]).fills
    exit_row = fills[fills["reason"] == "session_end"].iloc[0]
    assert pd.to_datetime(exit_row["fill_ts"], utc=True) == t1


def test_exit_ts_present_requires_no_session_params():
    t0 = pd.Timestamp("2025-04-03 14:35:00", tz="UTC")
    t1 = pd.Timestamp("2025-04-03 14:40:00", tz="UTC")
    bars = _bars([t0, t1], [100.0, 101.0], [100.5, 101.5], [99.5, 100.5])
    intent = pd.DataFrame(
        [
            {
                "template_id": "t1",
                "signal_ts": t0,
                "symbol": "HOOD",
                "side": "BUY",
                "entry_price": 100.0,
                "stop_price": 98.0,
                "take_profit_price": 104.0,
                "exit_ts": t1,
            }
        ]
    )
    fills = generate_fills(intent, bars).fills
    assert len(fills) == 2
