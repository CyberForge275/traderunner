from __future__ import annotations

import pandas as pd

from .config import InsideBarConfig
from .rules import eval_vectorized


def detect_inside_bars(df: pd.DataFrame, config: InsideBarConfig) -> pd.DataFrame:
    """
    Detect inside bar patterns (vectorized).

    Inside Bar Definition:
    - Current candle's high is AT OR BELOW previous candle's high (inclusive mode)
    - Current candle's low is AT OR ABOVE previous candle's low (inclusive mode)
    - OR strictly inside (strict mode)

    Mother Bar:
    - The candle immediately before the inside bar
    - Its high and low define breakout levels
    """
    df = df.copy()

    # Previous candle OHLC (mother bar)
    df['prev_high'] = df['high'].shift(1)
    df['prev_low'] = df['low'].shift(1)
    df['prev_open'] = df['open'].shift(1)
    df['prev_close'] = df['close'].shift(1)
    df['prev_range'] = df['prev_high'] - df['prev_low']

    strict = config.inside_bar_mode == "strict"
    inside_mask = eval_vectorized(df, config.inside_bar_definition_mode, strict)

    # Optional: Minimum mother bar size filter
    # (avoid patterns where mother bar is too small/noisy)
    if config.min_mother_bar_size > 0:
        # Mother bar range must be >= min_mother_size * ATR (mother bar ATR)
        atr_ref = df['atr'].shift(1)
        size_ok = (atr_ref > 0) & (
            df['prev_range'] >= (config.min_mother_bar_size * atr_ref)
        )
        inside_mask = inside_mask & size_ok.fillna(False)

    df['is_inside_bar'] = inside_mask
    df['mother_bar_high'] = df['prev_high'].where(inside_mask)
    df['mother_bar_low'] = df['prev_low'].where(inside_mask)

    return df
