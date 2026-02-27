from __future__ import annotations

import pandas as pd

from strategies.harami_break.pattern_detection import enrich_inside_pattern_frame
from strategies.harami_break.session_logic import apply_signal_validity


def _build_enriched_frame() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {"timestamp": "2026-02-20 14:30:00+00:00", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0},
            {"timestamp": "2026-02-20 14:35:00+00:00", "open": 101.0, "high": 108.0, "low": 92.0, "close": 103.0},
        ]
    )
    return enrich_inside_pattern_frame(
        df,
        definition_mode="mb_range_hl__ib_hl",
        strict=False,
        min_mother_body_fraction=0.0,
        max_mother_body_fraction=1.0,
        session_windows=["14:30-14:45"],
        session_timezone="UTC",
    )


def test_apply_signal_validity_session_window_end_uses_next_bar_exclusive() -> None:
    enriched = _build_enriched_frame()
    out = apply_signal_validity(
        enriched,
        timeframe_minutes=5,
        session_windows=["14:30-14:45"],
        session_timezone="UTC",
        order_validity_policy="session_window_end",
        order_validity_minutes=30,
        order_validity_bars=5,
    )
    assert bool(out.loc[1, "armed"]) is True
    assert out.loc[1, "armed_from_ts"] == pd.Timestamp("2026-02-20 14:40:00+00:00")
    assert out.loc[1, "valid_until_ts"] == pd.Timestamp("2026-02-20 14:45:00+00:00")
    assert bool(out.loc[1, "valid_window_ok"]) is True


def test_apply_signal_validity_fixed_minutes() -> None:
    enriched = _build_enriched_frame()
    out = apply_signal_validity(
        enriched,
        timeframe_minutes=5,
        session_windows=["14:30-14:45"],
        session_timezone="UTC",
        order_validity_policy="fixed_minutes",
        order_validity_minutes=20,
        order_validity_bars=5,
    )
    assert out.loc[1, "armed_from_ts"] == pd.Timestamp("2026-02-20 14:40:00+00:00")
    assert out.loc[1, "valid_until_ts"] == pd.Timestamp("2026-02-20 15:00:00+00:00")
    assert bool(out.loc[1, "valid_window_ok"]) is True


def test_apply_signal_validity_fixed_bars() -> None:
    enriched = _build_enriched_frame()
    out = apply_signal_validity(
        enriched,
        timeframe_minutes=5,
        session_windows=["14:30-14:45"],
        session_timezone="UTC",
        order_validity_policy="fixed_bars",
        order_validity_minutes=20,
        order_validity_bars=3,
    )
    assert out.loc[1, "armed_from_ts"] == pd.Timestamp("2026-02-20 14:40:00+00:00")
    assert out.loc[1, "valid_until_ts"] == pd.Timestamp("2026-02-20 14:55:00+00:00")
    assert bool(out.loc[1, "valid_window_ok"]) is True
