"""Independent impulse inspection helper.

This module composes the feature extraction and decision layer without
touching the existing sweet-spot scan/runtime flow.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .impulse_features import build_impulse_features
from .impulse_trigger import evaluate_impulse_trigger


def inspect_impulse_setup(
    daily_df: pd.DataFrame,
    *,
    symbol: str,
    breakout_date: str,
    pre_window: int,
    confirm_offset: int = 1,
    trim_top_n: int = 1,
    trim_bottom_n: int = 1,
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
    session_timezone: str = "America/New_York",
) -> dict[str, Any]:
    """Return one combined inspection record for a symbol/date breakout setup."""
    features = build_impulse_features(
        daily_df,
        symbol=symbol,
        breakout_date=breakout_date,
        pre_window=pre_window,
        confirm_offset=confirm_offset,
        trim_top_n=trim_top_n,
        trim_bottom_n=trim_bottom_n,
        session_timezone=session_timezone,
    )
    decision = evaluate_impulse_trigger(
        features,
        min_price_lr_trimmed=min_price_lr_trimmed,
        min_vol_lr_trimmed=min_vol_lr_trimmed,
        min_price_ratio_prev_to_breakout=min_price_ratio_prev_to_breakout,
        min_volume_ratio_prev_to_breakout=min_volume_ratio_prev_to_breakout,
        min_price_ratio_prev_to_confirm=min_price_ratio_prev_to_confirm,
        min_volume_ratio_prev_to_confirm=min_volume_ratio_prev_to_confirm,
        require_breakout_green=require_breakout_green,
        min_confirm_close_vs_breakout_close=min_confirm_close_vs_breakout_close,
        min_confirm_close_position_in_range=min_confirm_close_position_in_range,
        min_pre_max_drawdown=min_pre_max_drawdown,
        max_pre_gap_down_count=max_pre_gap_down_count,
    )
    return {**features, **decision}


__all__ = ["inspect_impulse_setup"]
