from __future__ import annotations

from typing import Tuple

import pandas as pd

MODE_MB_BODY_IB_HL = "mb_body_oc__ib_hl"
MODE_MB_BODY_IB_BODY = "mb_body_oc__ib_body"
MODE_MB_RANGE_IB_HL = "mb_range_hl__ib_hl"
MODE_MB_HIGH_IB_HIGH_AND_CLOSE_IN_MB_RANGE = "mb_high__ib_high_and_close_in_mb_range"

ALLOWED_DEFINITION_MODES = {
    MODE_MB_BODY_IB_HL,
    MODE_MB_BODY_IB_BODY,
    MODE_MB_RANGE_IB_HL,
    MODE_MB_HIGH_IB_HIGH_AND_CLOSE_IN_MB_RANGE,
}


def body_bounds(open_s: pd.Series, close_s: pd.Series) -> Tuple[pd.Series, pd.Series]:
    """Compute candle-body bounds for each row.

    Parameters:
    - open_s: Series of open prices.
    - close_s: Series of close prices.

    Returns:
    - Tuple (body_low, body_high) where each element is a Series:
      - body_low = min(open, close)
      - body_high = max(open, close)
    """
    body_low = pd.concat([open_s, close_s], axis=1).min(axis=1)
    body_high = pd.concat([open_s, close_s], axis=1).max(axis=1)
    return body_low, body_high


def _compare_bounds(
    ib_low: pd.Series,
    ib_high: pd.Series,
    mb_low: pd.Series,
    mb_high: pd.Series,
    strict: bool,
) -> pd.Series:
    """Compare inside-bar bounds against mother-bar bounds.

    Parameters:
    - ib_low: Lower bound of the inside candidate (range low or body low).
    - ib_high: Upper bound of the inside candidate (range high or body high).
    - mb_low: Lower bound of the mother reference (range low or body low).
    - mb_high: Upper bound of the mother reference (range high or body high).
    - strict:
      - True  -> strict containment (ib_high < mb_high and ib_low > mb_low)
      - False -> inclusive containment (ib_high <= mb_high and ib_low >= mb_low)

    Returns:
    - Boolean Series mask for rows that satisfy the containment rule.
    """
    if strict:
        return (ib_high < mb_high) & (ib_low > mb_low)
    return (ib_high <= mb_high) & (ib_low >= mb_low)


def eval_vectorized(
    df: pd.DataFrame,
    mode: str,
    strict: bool,
) -> pd.Series:
    """Evaluate inside-bar definition mode over a full DataFrame (vectorized).

    Parameters:
    - df: Input bars DataFrame. Required columns: open, high, low, close.
    - mode: One of ALLOWED_DEFINITION_MODES; selects which mother/inside bounds
      are compared.
    - strict:
      - True  -> strict inequalities for containment
      - False -> inclusive inequalities for containment

    Returns:
    - Boolean Series aligned to df index indicating whether each row is an
      inside-bar candidate relative to the immediately previous row.

    Notes:
    - Mother bar is always the previous bar (shift(1)).
    - Rows without a complete previous bar are filtered out via notna checks.
    """
    if mode not in ALLOWED_DEFINITION_MODES:
        raise ValueError(f"Invalid inside_bar_definition_mode: {mode}")

    prev_open = df["open"].shift(1)
    prev_close = df["close"].shift(1)
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)

    mb_body_low, mb_body_high = body_bounds(prev_open, prev_close)
    ib_body_low, ib_body_high = body_bounds(df["open"], df["close"])

    if mode == MODE_MB_BODY_IB_HL:
        inside_mask = _compare_bounds(df["low"], df["high"], mb_body_low, mb_body_high, strict)
    elif mode == MODE_MB_BODY_IB_BODY:
        inside_mask = _compare_bounds(ib_body_low, ib_body_high, mb_body_low, mb_body_high, strict)
    elif mode == MODE_MB_RANGE_IB_HL:
        inside_mask = _compare_bounds(df["low"], df["high"], prev_low, prev_high, strict)
    elif mode == MODE_MB_HIGH_IB_HIGH_AND_CLOSE_IN_MB_RANGE:
        if strict:
            inside_mask = (df["high"] < prev_high) & (df["close"] > prev_low) & (df["close"] < prev_high)
        else:
            inside_mask = (df["high"] <= prev_high) & (df["close"] >= prev_low) & (df["close"] <= prev_high)
    else:
        raise ValueError(f"Invalid inside_bar_definition_mode: {mode}")

    return (inside_mask & prev_open.notna() & prev_close.notna() & prev_high.notna() & prev_low.notna()).fillna(False)
