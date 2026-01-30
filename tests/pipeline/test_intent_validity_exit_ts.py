import pandas as pd

from axiom_bt.pipeline.signals import generate_intent


def test_intent_exit_ts_session_end_and_dbg_valid_to():
    ts = pd.Timestamp("2025-07-29 18:30:00+00:00")  # 14:30 NY
    signals_frame = pd.DataFrame(
        [
            {
                "template_id": "ib_tpl_1",
                "timestamp": ts,
                "symbol": "HOOD",
                "signal_side": "BUY",
                "entry_price": 100.0,
                "stop_price": 99.0,
                "take_profit_price": 102.0,
                "exit_ts": pd.NaT,
                "exit_reason": None,
            }
        ]
    )

    params = {
        "order_validity_policy": "session_end",
        "session_timezone": "America/New_York",
        "session_filter": ["09:30-11:00", "14:00-15:00"],
        "valid_from_policy": "signal_ts",
        "timeframe_minutes": 5,
    }

    artifacts = generate_intent(signals_frame, "insidebar_intraday", "1.0.1", params=params)
    row = artifacts.events_intent.iloc[0]

    expected_exit = pd.Timestamp("2025-07-29 19:00:00+00:00")  # 15:00 NY
    assert pd.Timestamp(row["exit_ts"]).tz_convert("UTC") == expected_exit
    assert row["exit_reason"] == "session_end"
    assert pd.Timestamp(row["dbg_valid_to_ts_utc"]).tz_convert("UTC") == expected_exit
    assert pd.Timestamp(row["dbg_valid_to_ts_ny"]).tz_convert("America/New_York").time() == pd.Timestamp("15:00").time()
