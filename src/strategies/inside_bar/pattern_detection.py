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
    df['prev_body'] = (df['prev_close'] - df['prev_open']).abs()
    df['inside_range'] = df['high'] - df['low']
    df['inside_body'] = (df['close'] - df['open']).abs()
    df['mother_body_fraction'] = (
        (df['prev_body'] / df['prev_range']).where(df['prev_range'] > 0, 0.0).fillna(0.0)
    )
    df['inside_body_fraction'] = (
        (df['inside_body'] / df['inside_range']).where(df['inside_range'] > 0, 0.0).fillna(0.0)
    )
    df['inside_bar_reject_reason'] = pd.NA

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

    # Quality gate: reject wick/doji-heavy mother bars.
    mb_ok = df['mother_body_fraction'] >= config.min_mother_body_fraction
    mb_reject = inside_mask & (~mb_ok.fillna(False))
    df.loc[mb_reject, 'inside_bar_reject_reason'] = 'MB_BODY_FRACTION'
    inside_mask = inside_mask & mb_ok.fillna(False)

    # Quality gate: reject tiny-body inside bars.
    ib_ok = df['inside_body_fraction'] >= config.min_inside_body_fraction
    ib_reject = inside_mask & (~ib_ok.fillna(False))
    df.loc[ib_reject, 'inside_bar_reject_reason'] = 'IB_BODY_FRACTION'
    inside_mask = inside_mask & ib_ok.fillna(False)

    df['is_inside_bar'] = inside_mask
    df['mother_bar_high'] = df['prev_high'].where(inside_mask)
    df['mother_bar_low'] = df['prev_low'].where(inside_mask)

    return df
