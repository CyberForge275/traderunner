from __future__ import annotations

import pandas as pd

from strategies.harami_break.intent_generation import generate_intent


def _row(
    ts: str,
    *,
    armed: bool,
    valid: bool,
    mh: float,
    ml: float,
    mother_open: float = 100.0,
    mother_close: float = 101.0,
    inside_open: float = 100.0,
    inside_close: float = 101.0,
) -> dict:
    t = pd.Timestamp(ts, tz="UTC")
    return {
        "timestamp": t,
        "mother_bar_ts": t - pd.Timedelta(minutes=5),
        "symbol": "HOOD",
        "armed": armed,
        "valid_window_ok": valid,
        "armed_from_ts": t + pd.Timedelta(minutes=5),
        "valid_until_ts": t + pd.Timedelta(minutes=30),
        "long_trigger_price": mh,
        "short_trigger_price": ml,
        "mother_bar_high": mh,
        "mother_bar_low": ml,
        "prev_open": mother_open,
        "prev_close": mother_close,
        "open": inside_open,
        "close": inside_close,
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
            "regime_filter": {
                "enabled": False,
                "allow_gg_short": True,
                "allow_mixed_short": True,
            },
        },
    )

    events = art.events_intent
    assert len(events) == 2
    assert set(events["side"]) == {"BUY", "SELL"}
    assert events["oco_group_id"].nunique() == 1
    assert events["order_valid_from_ts"].notna().all()
    assert (events["order_valid_to_reason"] == "session_end").all()
    assert events["order_valid_to_ts"].notna().all()
    assert events["entry_price"].notna().all()
    assert events["stop_price"].notna().all()
    assert events["take_profit_price"].notna().all()
    for col in (
        "sig_LONG_entry_price",
        "sig_LONG_stop_price",
        "sig_LONG_take_profit_price",
        "sig_SHORT_entry_price",
        "sig_SHORT_stop_price",
        "sig_SHORT_take_profit_price",
        "dbg_mother_ts",
        "dbg_inside_ts",
        "dbg_mother_high",
        "dbg_mother_low",
        "dbg_mother_range",
    ):
        assert col in events.columns
    assert events["sig_LONG_entry_price"].nunique() == 1
    assert events["sig_SHORT_entry_price"].nunique() == 1
    assert events["dbg_mother_ts"].nunique() == 1
    assert events["dbg_inside_ts"].nunique() == 1


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
            "regime_filter": {
                "enabled": False,
                "allow_gg_short": True,
                "allow_mixed_short": True,
            },
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
            "regime_filter": {
                "enabled": False,
                "allow_gg_short": True,
                "allow_mixed_short": True,
            },
        },
    )
    # One setup allowed -> two OCO legs.
    assert len(art.events_intent) == 2


def test_generate_intent_filters_short_for_green_green_when_configured() -> None:
    frame = pd.DataFrame(
        [
            _row(
                "2026-02-20 15:05:00",
                armed=True,
                valid=True,
                mh=110.0,
                ml=106.0,
                mother_open=100.0,
                mother_close=101.0,  # green mother
                inside_open=100.5,
                inside_close=101.2,  # green inside
            )
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
            "regime_filter": {
                "enabled": True,
                "allow_gg_short": False,
                "allow_mixed_short": True,
            },
        },
    )
    assert set(art.events_intent["side"]) == {"BUY"}
    row = art.events_intent.iloc[0]
    assert row["sig_SHORT_entry_price"] == 106.0
    assert row["sig_SHORT_stop_price"] == 110.0
    assert row["sig_SHORT_take_profit_price"] == 102.0


def test_generate_intent_filters_short_for_mixed_when_configured() -> None:
    frame = pd.DataFrame(
        [
            _row(
                "2026-02-20 15:05:00",
                armed=True,
                valid=True,
                mh=110.0,
                ml=106.0,
                mother_open=100.0,
                mother_close=101.0,  # green mother
                inside_open=101.0,
                inside_close=100.2,  # red inside -> mixed
            )
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
            "regime_filter": {
                "enabled": True,
                "allow_gg_short": True,
                "allow_mixed_short": False,
            },
        },
    )
    assert set(art.events_intent["side"]) == {"BUY"}
    row = art.events_intent.iloc[0]
    assert row["sig_SHORT_entry_price"] == 106.0
    assert row["sig_SHORT_stop_price"] == 110.0
    assert row["sig_SHORT_take_profit_price"] == 102.0
