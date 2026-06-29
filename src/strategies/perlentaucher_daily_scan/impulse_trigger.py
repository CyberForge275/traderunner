"""Pure decision layer for impulse-based breakout screening.

This module consumes the output of `impulse_features.py` and turns it into
explicit pass/fail flags plus one deterministic reason code.
"""

from __future__ import annotations

import math
from typing import Any


def _as_float(mapping: dict[str, Any], key: str) -> float:
    value = mapping.get(key, float("nan"))
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _is_present(value: float) -> bool:
    return not math.isnan(value)


def evaluate_impulse_trigger(
    features: dict[str, Any],
    *,
    min_price_lr_trimmed: float,
    min_vol_lr_trimmed: float,
    min_price_ratio_prev_to_breakout: float,
    min_volume_ratio_prev_to_breakout: float,
    min_price_ratio_prev_to_confirm: float,
    min_volume_ratio_prev_to_confirm: float,
    require_breakout_green: bool = True,
    min_confirm_close_vs_breakout_close: float = 0.98,
    min_confirm_close_position_in_range: float = 0.50,
    min_pre_max_drawdown: float = -0.35,
    max_pre_gap_down_count: int = 4,
) -> dict[str, Any]:
    """Evaluate one impulse setup with explicit threshold semantics."""
    price_lr_trimmed = _as_float(features, "price_lr_trimmed")
    vol_lr_trimmed = _as_float(features, "vol_lr_trimmed")
    price_ratio_prev_to_breakout = _as_float(features, "price_ratio_prev_to_breakout")
    volume_ratio_prev_to_breakout = _as_float(features, "volume_ratio_prev_to_breakout")
    price_ratio_prev_to_confirm = _as_float(features, "price_ratio_prev_to_confirm")
    volume_ratio_prev_to_confirm = _as_float(features, "volume_ratio_prev_to_confirm")
    breakout_green = bool(features.get("breakout_green", False))
    confirm_close_vs_breakout_close = _as_float(features, "confirm_close_vs_breakout_close")
    confirm_close_position_in_range = _as_float(features, "confirm_close_position_in_range")
    pre_max_drawdown = _as_float(features, "pre_max_drawdown")
    pre_gap_down_count = features.get("pre_gap_down_count")
    try:
        pre_gap_down_count = int(pre_gap_down_count)
    except (TypeError, ValueError):
        pre_gap_down_count = None

    precondition_passed = (
        _is_present(price_lr_trimmed)
        and _is_present(vol_lr_trimmed)
        and price_lr_trimmed >= float(min_price_lr_trimmed)
        and vol_lr_trimmed >= float(min_vol_lr_trimmed)
    )
    prewindow_path_passed = (
        _is_present(pre_max_drawdown)
        and pre_max_drawdown >= float(min_pre_max_drawdown)
        and pre_gap_down_count is not None
        and pre_gap_down_count <= int(max_pre_gap_down_count)
    )

    breakout_passed = (
        _is_present(price_ratio_prev_to_breakout)
        and _is_present(volume_ratio_prev_to_breakout)
        and price_ratio_prev_to_breakout >= float(min_price_ratio_prev_to_breakout)
        and volume_ratio_prev_to_breakout >= float(min_volume_ratio_prev_to_breakout)
    )
    breakout_bar_passed = (not require_breakout_green) or breakout_green

    confirm_data_present = (
        _is_present(price_ratio_prev_to_confirm)
        and _is_present(volume_ratio_prev_to_confirm)
    )
    confirmation_close_passed = (
        _is_present(confirm_close_vs_breakout_close)
        and confirm_close_vs_breakout_close >= float(min_confirm_close_vs_breakout_close)
    )
    confirmation_range_position_passed = (
        _is_present(confirm_close_position_in_range)
        and confirm_close_position_in_range >= float(min_confirm_close_position_in_range)
    )
    confirmation_passed = (
        confirm_data_present
        and price_ratio_prev_to_confirm >= float(min_price_ratio_prev_to_confirm)
        and volume_ratio_prev_to_confirm >= float(min_volume_ratio_prev_to_confirm)
        and confirmation_close_passed
        and confirmation_range_position_passed
    )

    if not precondition_passed:
        trigger_reason = "PRECONDITION_FAILED"
    elif not prewindow_path_passed:
        trigger_reason = "PREWINDOW_PATH_REJECTED"
    elif not breakout_passed:
        trigger_reason = "BREAKOUT_THRESHOLD_FAILED"
    elif not breakout_bar_passed:
        trigger_reason = "BREAKOUT_BAR_REJECTED"
    elif not confirm_data_present:
        trigger_reason = "CONFIRMATION_DATA_MISSING"
    elif not confirmation_close_passed:
        trigger_reason = "CONFIRMATION_CLOSE_REJECTED"
    elif not confirmation_range_position_passed:
        trigger_reason = "CONFIRMATION_RANGE_POSITION_REJECTED"
    elif not confirmation_passed:
        trigger_reason = "CONFIRMATION_THRESHOLD_FAILED"
    else:
        trigger_reason = "IMPULSE_CONFIRMED"

    return {
        "trigger_passed": trigger_reason == "IMPULSE_CONFIRMED",
        "trigger_reason": trigger_reason,
        "precondition_passed": precondition_passed,
        "prewindow_path_passed": prewindow_path_passed,
        "breakout_passed": breakout_passed,
        "breakout_bar_passed": breakout_bar_passed,
        "confirmation_passed": confirmation_passed,
        "confirmation_close_passed": confirmation_close_passed,
        "confirmation_range_position_passed": confirmation_range_position_passed,
        "price_lr_trimmed": price_lr_trimmed,
        "vol_lr_trimmed": vol_lr_trimmed,
        "breakout_green": breakout_green,
        "confirm_close_vs_breakout_close": confirm_close_vs_breakout_close,
        "confirm_close_position_in_range": confirm_close_position_in_range,
        "pre_max_drawdown": pre_max_drawdown,
        "pre_gap_down_count": pre_gap_down_count,
        "price_ratio_prev_to_breakout": price_ratio_prev_to_breakout,
        "volume_ratio_prev_to_breakout": volume_ratio_prev_to_breakout,
        "price_ratio_prev_to_confirm": price_ratio_prev_to_confirm,
        "volume_ratio_prev_to_confirm": volume_ratio_prev_to_confirm,
    }


__all__ = ["evaluate_impulse_trigger"]
