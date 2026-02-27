from __future__ import annotations

import pandas as pd

from strategies.harami_break.intent_generation import generate_intent


def _row(ts: str, *, armed: bool, valid: bool, mh: float, ml: float) -> dict:
    t = pd.Timestamp(ts, tz="UTC")
    return {
        "timestamp": t,
        "symbol": "HOOD",
        "armed": armed,
        "valid_window_ok": valid,
        "armed_from_ts": t + pd.Timedelta(minutes=5),
        "valid_until_ts": t + pd.Timedelta(minutes=30),
        "long_trigger_price": mh,
        "short_trigger_price": ml,
        "mother_bar_high": mh,
        "mother_bar_low": ml,
    }


def test_generate_intent_emits_oco_legs_for_valid_setup() -> None:
    frame = pd.DataFrame([_row("2026-02-20 15:05:00", armed=True, valid=True, mh=110.0, ml=106.0)])
    art = generate_intent(
        frame,
        "harami_break_intraday",
        "1.0.0",
        {
            "session_timezone": "America/New_York",
            "session_windows": ["09:30-11:00", "14:00-15:30"],
            "order_validity_policy": "session_end",
            "max_trades_per_session_window": 1,
        },
    )

    events = art.events_intent
    assert len(events) == 2
    assert set(events["side"]) == {"BUY", "SELL"}
    assert events["oco_group_id"].nunique() == 1
    assert (events["order_valid_to_reason"] == "session_end").all()
    assert events["order_valid_to_ts"].notna().all()
    assert events["entry_price"].notna().all()
    assert events["stop_price"].notna().all()
    assert events["take_profit_price"].notna().all()


def test_generate_intent_skips_rows_without_valid_window() -> None:
    frame = pd.DataFrame([_row("2026-02-20 15:05:00", armed=True, valid=False, mh=110.0, ml=106.0)])
    art = generate_intent(
        frame,
        "harami_break_intraday",
        "1.0.0",
        {
            "session_timezone": "America/New_York",
            "session_windows": ["09:30-11:00", "14:00-15:30"],
            "order_validity_policy": "session_end",
            "max_trades_per_session_window": 1,
        },
    )
    assert art.events_intent.empty


def test_generate_intent_respects_max_trades_per_session_window() -> None:
    frame = pd.DataFrame(
        [
            _row("2026-02-20 15:05:00", armed=True, valid=True, mh=110.0, ml=106.0),
            _row("2026-02-20 15:15:00", armed=True, valid=True, mh=109.0, ml=105.0),
        ]
    )
    art = generate_intent(
        frame,
        "harami_break_intraday",
        "1.0.0",
        {
            "session_timezone": "America/New_York",
            "session_windows": ["09:30-11:00", "14:00-15:30"],
            "order_validity_policy": "session_end",
            "max_trades_per_session_window": 1,
        },
    )
    # One setup allowed -> two OCO legs.
    assert len(art.events_intent) == 2
