from __future__ import annotations

import pandas as pd

from axiom_bt.pipeline.signal_frame_factory import build_signal_frame


def _bars() -> pd.DataFrame:
    ts = pd.date_range("2026-02-20 14:30:00", periods=10, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0, 101.0, 102.0, 101.5, 101.2, 101.3, 101.1, 101.0, 100.9, 101.0],
            "high": [101.2, 102.0, 102.5, 101.9, 101.5, 101.7, 101.4, 101.3, 101.2, 101.2],
            "low": [99.8, 100.5, 101.2, 100.9, 100.8, 100.9, 100.7, 100.6, 100.5, 100.6],
            "close": [101.0, 101.8, 101.6, 101.1, 101.3, 101.2, 101.0, 100.9, 101.0, 101.1],
            "volume": [100] * 10,
        }
    )


def test_harami_signal_frame_builds_via_registry_plugin():
    df, schema = build_signal_frame(
        _bars(),
        "harami_break_intraday",
        "1.0.0",
        {
            "symbol": "HOOD",
            "timeframe": "M5",
            "inside_bar_definition_mode": "mb_range_hl__ib_hl",
            "strict_mode": False,
            "min_mother_body_fraction": 0.0,
            "max_mother_body_fraction": 1.0,
            "session_windows": ["09:30-11:00", "14:00-15:30"],
            "session_timezone": "America/New_York",
            "timeframe_minutes": 5,
            "order_validity_policy": "session_end",
            "order_validity_minutes": 30,
            "order_validity_bars": 5,
        },
    )
    assert not df.empty
    assert schema.strategy_id == "harami_break_intraday"
    assert "is_inside_bar" in df.columns
    assert "mother_body_fraction" in df.columns
    assert "mother_body_ok" in df.columns
    assert "armed_from_ts" in df.columns
