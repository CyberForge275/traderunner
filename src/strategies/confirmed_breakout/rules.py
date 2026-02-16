from __future__ import annotations

import logging
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)

MODE_MB_BODY_IB_HL = "mb_body_oc__ib_hl"
MODE_MB_BODY_IB_BODY = "mb_body_oc__ib_body"
MODE_MB_RANGE_IB_HL = "mb_range_hl__ib_hl"
MODE_MB_HIGH_IB_HIGH_AND_CLOSE_IN_MB_RANGE = "mb_high__ib_high_and_close_in_mb_range"

ALLOWED_MODES = {
    MODE_MB_BODY_IB_HL,
    MODE_MB_BODY_IB_BODY,
    MODE_MB_RANGE_IB_HL,
    MODE_MB_HIGH_IB_HIGH_AND_CLOSE_IN_MB_RANGE,
}


def body_bounds(open_s: pd.Series, close_s: pd.Series) -> Tuple[pd.Series, pd.Series]:
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
    if strict:
        return (ib_high < mb_high) & (ib_low > mb_low)
    return (ib_high <= mb_high) & (ib_low >= mb_low)


def eval_vectorized(
    df: pd.DataFrame,
    mode: str,
    strict: bool,
) -> pd.Series:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Invalid inside_bar_definition_mode: {mode}")

    logger.info(
        "actions: insidebar_rule_eval mode=%s strict=%s rows=%d",
        mode,
        strict,
        len(df),
    )

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

    # Ensure previous bar exists
    inside_mask = inside_mask & prev_open.notna() & prev_close.notna() & prev_high.notna() & prev_low.notna()

    return inside_mask.fillna(False)


def eval_scalar(
    *,
    mb_open: float,
    mb_close: float,
    mb_high: float,
    mb_low: float,
    ib_open: float,
    ib_close: float,
    ib_high: float,
    ib_low: float,
    mode: str,
    strict: bool,
) -> bool:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Invalid inside_bar_definition_mode: {mode}")

    mb_body_low = min(mb_open, mb_close)
    mb_body_high = max(mb_open, mb_close)
    ib_body_low = min(ib_open, ib_close)
    ib_body_high = max(ib_open, ib_close)

    if mode == MODE_MB_BODY_IB_HL:
        if strict:
            return ib_high < mb_body_high and ib_low > mb_body_low
        return ib_high <= mb_body_high and ib_low >= mb_body_low
    if mode == MODE_MB_BODY_IB_BODY:
        if strict:
            return ib_body_high < mb_body_high and ib_body_low > mb_body_low
        return ib_body_high <= mb_body_high and ib_body_low >= mb_body_low
    if mode == MODE_MB_RANGE_IB_HL:
        if strict:
            return ib_high < mb_high and ib_low > mb_low
        return ib_high <= mb_high and ib_low >= mb_low
    if mode == MODE_MB_HIGH_IB_HIGH_AND_CLOSE_IN_MB_RANGE:
        if strict:
            return ib_high < mb_high and mb_low < ib_close < mb_high
        return ib_high <= mb_high and mb_low <= ib_close <= mb_high

    raise ValueError(f"Invalid inside_bar_definition_mode: {mode}")
