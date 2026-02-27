from __future__ import annotations

import pandas as pd

from strategies.harami_break.pattern_detection import (
    detect_inside_pattern,
    enrich_inside_pattern_frame,
)
from strategies.harami_break.rules import ALLOWED_DEFINITION_MODES
from strategies.config.managers.harami_break_manager import HaramiBreakConfigManager


def test_definition_modes_are_available_for_harami_break() -> None:
    assert ALLOWED_DEFINITION_MODES == {
        "mb_body_oc__ib_hl",
        "mb_body_oc__ib_body",
        "mb_range_hl__ib_hl",
        "mb_high__ib_high_and_close_in_mb_range",
    }


def test_detect_inside_pattern_uses_definition_mode() -> None:
    df = pd.DataFrame(
        [
            {"open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0},
            {"open": 101.0, "high": 108.0, "low": 92.0, "close": 103.0},
        ]
    )
    mask = detect_inside_pattern(df, definition_mode="mb_range_hl__ib_hl", strict=False)
    assert list(mask.astype(bool)) == [False, True]


def test_harami_config_loads_without_required_warmup_bars() -> None:
    manager = HaramiBreakConfigManager()
    node = manager.get("1.0.0")
    assert "required_warmup_bars" not in node
    assert "inside_bar_mode" not in node["core"]
    assert "inside_bar_mode" not in manager.get_field_specs()["core"]
    assert "min_mother_body_fraction" in node["core"]
    assert "max_mother_body_fraction" in node["core"]
    assert "min_mother_body_fraction" in manager.get_field_specs()["core"]
    assert "max_mother_body_fraction" in manager.get_field_specs()["core"]
    tz_spec = manager.get_field_specs()["core"]["session_timezone"]
    assert tz_spec["kind"] == "enum"
    assert sorted(tz_spec["options"]) == ["America/New_York", "Europe/Berlin"]


def test_enrich_inside_pattern_frame_adds_motherbar_columns() -> None:
    ts0 = pd.Timestamp("2026-02-20 14:30:00+00:00")
    ts1 = pd.Timestamp("2026-02-20 14:35:00+00:00")
    df = pd.DataFrame(
        [
            {"timestamp": ts0, "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0},
            {"timestamp": ts1, "open": 101.0, "high": 108.0, "low": 92.0, "close": 103.0},
        ]
    )
    out = enrich_inside_pattern_frame(
        df,
        definition_mode="mb_range_hl__ib_hl",
        strict=False,
        min_mother_body_fraction=0.0,
        max_mother_body_fraction=1.0,
    )
    assert "is_inside_bar" in out.columns
    assert "is_motherbar" in out.columns
    assert "mother_bar_high" in out.columns
    assert "mother_bar_low" in out.columns
    assert "mother_bar_ts" in out.columns
    assert bool(out.loc[0, "is_motherbar"]) is True
    assert bool(out.loc[1, "is_inside_bar"]) is True
    assert float(out.loc[1, "mother_bar_high"]) == 110.0
    assert float(out.loc[1, "mother_bar_low"]) == 90.0
    assert out.loc[1, "mother_bar_ts"] == ts0


def test_enrich_inside_pattern_frame_sets_armed_from_session_windows() -> None:
    df = pd.DataFrame(
        [
            {"timestamp": "2026-02-20 14:30:00+00:00", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0},
            {"timestamp": "2026-02-20 14:35:00+00:00", "open": 101.0, "high": 108.0, "low": 92.0, "close": 103.0},
            {"timestamp": "2026-02-20 16:30:00+00:00", "open": 200.0, "high": 210.0, "low": 190.0, "close": 205.0},
            {"timestamp": "2026-02-20 16:35:00+00:00", "open": 201.0, "high": 208.0, "low": 192.0, "close": 203.0},
        ]
    )
    out = enrich_inside_pattern_frame(
        df,
        definition_mode="mb_range_hl__ib_hl",
        strict=False,
        min_mother_body_fraction=0.0,
        max_mother_body_fraction=1.0,
        session_windows=["14:30-14:40"],
        session_timezone="UTC",
    )
    assert bool(out.loc[1, "is_inside_bar"]) is True
    assert bool(out.loc[3, "is_inside_bar"]) is True
    assert bool(out.loc[1, "armed"]) is True
    assert bool(out.loc[3, "armed"]) is False


def test_enrich_inside_pattern_frame_filters_by_mother_body_fraction_band() -> None:
    df = pd.DataFrame(
        [
            {"timestamp": "2026-02-20 14:30:00+00:00", "open": 100.0, "high": 120.0, "low": 90.0, "close": 119.0},
            {"timestamp": "2026-02-20 14:35:00+00:00", "open": 101.0, "high": 108.0, "low": 92.0, "close": 103.0},
            {"timestamp": "2026-02-20 14:40:00+00:00", "open": 200.0, "high": 210.0, "low": 190.0, "close": 207.0},
            {"timestamp": "2026-02-20 14:45:00+00:00", "open": 201.0, "high": 208.0, "low": 192.0, "close": 203.0},
        ]
    )
    out = enrich_inside_pattern_frame(
        df,
        definition_mode="mb_range_hl__ib_hl",
        strict=False,
        min_mother_body_fraction=0.2,
        max_mother_body_fraction=0.6,
    )
    assert bool(out.loc[1, "is_inside_bar"]) is True
    assert bool(out.loc[3, "is_inside_bar"]) is True
    assert bool(out.loc[1, "mother_body_ok"]) is False
    assert bool(out.loc[1, "armed"]) is False
    assert bool(out.loc[3, "mother_body_ok"]) is True
    assert bool(out.loc[3, "armed"]) is True
