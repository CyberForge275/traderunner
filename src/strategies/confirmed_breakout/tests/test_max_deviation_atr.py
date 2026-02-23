from __future__ import annotations

import pandas as pd

from ..core import InsideBarCore, InsideBarConfig


def _cfg(**overrides) -> InsideBarConfig:
    base = {
        "inside_bar_definition_mode": "mb_range_hl__ib_hl",
        "atr_period": 1,
        "risk_reward_ratio": 2.0,
        "min_mother_bar_size": 0.0,
        "breakout_confirmation": True,
        "inside_bar_mode": "inclusive",
        "session_timezone": "UTC",
        "session_windows": ["00:00-23:59"],
        "timeframe_minutes": 5,
        "order_validity_policy": "session_end",
        "valid_from_policy": "signal_ts",
        "stop_cap_atr": 4000,
        "max_position_pct": 100.0,
        "max_deviation_atr": 3.0,
    }
    base.update(overrides)
    return InsideBarConfig(**base)


def _bars_for_deviation_test() -> pd.DataFrame:
    ts = pd.date_range("2025-01-01 09:30", periods=4, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0, 101.0, 105.0, 105.0],
            "high": [101.0, 110.0, 106.0, 106.0],
            "low": [99.0, 100.0, 104.0, 104.0],
            "close": [100.0, 108.0, 105.0, 105.0],
            "volume": [1000, 1000, 1000, 1000],
        }
    )


def test_max_deviation_atr_rejects_far_entry_levels():
    core = InsideBarCore(_cfg(max_deviation_atr=0.2))
    out = core.process_data(_bars_for_deviation_test(), "TEST")
    assert out == []


def test_max_deviation_atr_allows_when_within_threshold():
    core = InsideBarCore(_cfg(max_deviation_atr=10.0))
    out = core.process_data(_bars_for_deviation_test(), "TEST")
    assert len(out) >= 1
