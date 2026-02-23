from __future__ import annotations

import pandas as pd

from ..intent_generation import generate_intent


def _signals_frame(ts: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": ts,
                "template_id": "cb_TEST_20250101_150000_BUY",
                "symbol": "TEST",
                "signal_side": "BUY",
                "oco_group_id": "oco_1",
                "entry_price": 100.0,
                "stop_price": 99.0,
                "take_profit_price": 102.0,
            }
        ]
    )


def test_pattern_age_caps_order_valid_to_before_session_end():
    frame = _signals_frame("2025-01-01T15:00:00Z")
    params = {
        "order_validity_policy": "session_end",
        "session_timezone": "America/New_York",
        "session_filter": ["09:30-16:00"],
        "valid_from_policy": "signal_ts",
        "timeframe_minutes": 5,
        "max_pattern_age_candles": 2,
        "breakout_confirmation": True,
    }

    out = generate_intent(frame, "confirmed_breakout_intraday", "1.0.1", params)
    valid_to = pd.to_datetime(out.events_intent.iloc[0]["order_valid_to_ts"], utc=True)
    assert valid_to == pd.Timestamp("2025-01-01T15:10:00Z")


def test_pattern_age_none_keeps_session_end_valid_to():
    frame = _signals_frame("2025-01-01T15:00:00Z")
    params = {
        "order_validity_policy": "session_end",
        "session_timezone": "America/New_York",
        "session_filter": ["09:30-16:00"],
        "valid_from_policy": "signal_ts",
        "timeframe_minutes": 5,
        "max_pattern_age_candles": None,
        "breakout_confirmation": True,
    }

    out = generate_intent(frame, "confirmed_breakout_intraday", "1.0.1", params)
    valid_to = pd.to_datetime(out.events_intent.iloc[0]["order_valid_to_ts"], utc=True)
    assert valid_to == pd.Timestamp("2025-01-01T21:00:00Z")
