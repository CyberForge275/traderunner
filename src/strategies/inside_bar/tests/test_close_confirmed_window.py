import pandas as pd

from ..core import InsideBarCore, InsideBarConfig


def _cfg(**overrides):
    base = {
        "inside_bar_definition_mode": "mb_body_oc__ib_hl",
        "atr_period": 1,
        "risk_reward_ratio": 2.0,
        "min_mother_bar_size": 0.0,
        "breakout_confirmation": True,
        "breakout_confirmation_mode": "close",
        "inside_bar_mode": "inclusive",
        "session_timezone": "UTC",
        "session_windows": ["00:00-23:59"],
        "timeframe_minutes": 5,
        "order_validity_policy": "session_end",
        "valid_from_policy": "next_bar",
        "stop_cap_atr": 10.0,
        "max_position_pct": 100.0,
        "max_breakout_range_bars": 4,
        "max_pattern_age_candles": 12,
        "max_deviation_atr": None,
        "max_position_loss_pct_equity": None,
        "min_mother_body_fraction": 0.0,
        "min_inside_body_fraction": 0.0,
    }
    base.update(overrides)
    return InsideBarConfig(**base)


def test_close_confirmed_requires_close_cross_and_enters_next_bar():
    ts = pd.date_range("2025-01-01 14:00:00", periods=8, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0, 100.0, 101.2, 102.7, 103.0, 103.1, 103.0, 102.9],
            "high": [101.0, 103.0, 101.8, 103.4, 103.5, 103.4, 103.2, 103.1],
            "low": [99.5, 99.0, 100.8, 101.8, 102.8, 102.7, 102.6, 102.5],
            "close": [100.5, 102.0, 101.4, 102.9, 103.2, 103.1, 103.0, 102.8],
        }
    )
    core = InsideBarCore(_cfg())
    signals = core.process_data(df, "TEST")

    assert len(signals) == 1
    assert signals[0].side == "BUY"
    # close-confirmation is on bar index 4 -> valid_from/entry earliest on next bar index 5
    assert pd.to_datetime(signals[0].timestamp, utc=True) == ts[5]


def test_close_confirmed_expires_after_window_of_4_bars():
    ts = pd.date_range("2025-01-01 14:00:00", periods=9, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0, 100.0, 101.2, 102.0, 102.1, 102.2, 102.0, 103.1, 103.0],
            "high": [101.0, 103.0, 101.8, 103.3, 103.2, 103.1, 103.2, 103.6, 103.4],
            "low": [99.5, 99.0, 100.8, 101.7, 101.8, 101.9, 101.8, 102.8, 102.7],
            # bars 3..6 do not close > 103.0 (mother high), bar 7 closes above but too late
            "close": [100.5, 102.0, 101.4, 102.7, 102.8, 102.9, 102.95, 103.2, 103.0],
        }
    )
    core = InsideBarCore(_cfg())
    signals = core.process_data(df, "TEST")

    assert len(signals) == 0
