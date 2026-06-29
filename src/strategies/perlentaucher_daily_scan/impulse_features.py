"""Strategy-local impulse feature helpers for breakout research.

This module keeps the breakout analysis logic parameter-driven:
- the pre-window length is passed by the caller
- spike trimming is passed by the caller
- the external marketdata handoff remains unchanged
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .market_dates import market_date_series


def _as_market_date_series(ts: pd.Series, session_timezone: str) -> pd.Series:
    return market_date_series(
        ts,
        session_timezone=session_timezone,
        error_prefix="impulse_features bars",
    ).astype(str)


def _linear_regression_slope(values: np.ndarray) -> float:
    if len(values) <= 1:
        return float("nan")
    x = np.arange(len(values), dtype=float)
    y = np.asarray(values, dtype=float)
    sum_x = x.sum()
    sum_x2 = np.square(x).sum()
    denom = len(x) * sum_x2 - sum_x * sum_x
    if denom == 0:
        return float("nan")
    sum_y = y.sum()
    sum_xy = np.dot(x, y)
    return float((len(x) * sum_xy - sum_x * sum_y) / denom)


def compute_window_lr(values: pd.Series, window: int) -> float:
    """Return the LR slope for the trailing window.

    The function is intentionally window-agnostic; callers decide whether
    they want 20, 30, 40, or any other lookback for research/backtesting.
    """
    if window <= 1:
        raise ValueError("window must be > 1")
    series = pd.to_numeric(values, errors="coerce").dropna().reset_index(drop=True)
    if len(series) < window:
        return float("nan")
    window_values = series.iloc[-window:].to_numpy(dtype=float, copy=False)
    return _linear_regression_slope(window_values)


def compute_trimmed_window_lr(
    values: pd.Series,
    window: int,
    *,
    trim_top_n: int = 1,
    trim_bottom_n: int = 1,
) -> float:
    """Return LR slope after dropping the largest/smallest spikes in-window.

    Trimming is done on values, while preserving the remaining chronological
    order so the resulting slope still represents the filtered path.
    """
    if window <= 1:
        raise ValueError("window must be > 1")
    if trim_top_n < 0 or trim_bottom_n < 0:
        raise ValueError("trim counts must be >= 0")

    series = pd.to_numeric(values, errors="coerce").dropna().reset_index(drop=True)
    if len(series) < window:
        return float("nan")

    window_series = series.iloc[-window:].copy()
    if trim_top_n + trim_bottom_n >= len(window_series):
        raise ValueError("trim counts remove the entire window")

    drop_idx: set[int] = set()
    if trim_top_n:
        drop_idx.update(window_series.nlargest(trim_top_n).index.tolist())
    if trim_bottom_n:
        drop_idx.update(window_series.nsmallest(trim_bottom_n).index.tolist())

    trimmed = window_series.drop(index=list(drop_idx)).reset_index(drop=True)
    return _linear_regression_slope(trimmed.to_numpy(dtype=float, copy=False))


def compute_ratio(current: float, previous: float) -> float:
    if pd.isna(current) or pd.isna(previous):
        return float("nan")
    previous_f = float(previous)
    if previous_f == 0.0:
        return float("nan")
    return float(float(current) / previous_f)


def compute_max_drawdown(values: pd.Series) -> float:
    series = pd.to_numeric(values, errors="coerce").dropna().reset_index(drop=True)
    if series.empty:
        return float("nan")
    running_max = series.cummax()
    drawdown = (series / running_max) - 1.0
    return float(drawdown.min())


def compute_close_position_in_range(
    *,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
) -> float:
    _ = open_price
    range_size = float(high_price) - float(low_price)
    if range_size == 0.0:
        return float("nan")
    return float((float(close_price) - float(low_price)) / range_size)


def build_impulse_features(
    daily_df: pd.DataFrame,
    *,
    symbol: str,
    breakout_date: str,
    pre_window: int,
    confirm_offset: int = 1,
    trim_top_n: int = 1,
    trim_bottom_n: int = 1,
    session_timezone: str = "America/New_York",
) -> dict[str, Any]:
    """Build one breakout impulse feature record for a single symbol/date.

    The pre-window ends on the trading day immediately before the breakout.
    Confirmation is based on the trading day `confirm_offset` bars after the
    breakout date, if such a bar exists.
    """
    if daily_df.empty:
        raise ValueError("daily_df cannot be empty")
    if pre_window <= 1:
        raise ValueError("pre_window must be > 1")
    if confirm_offset < 1:
        raise ValueError("confirm_offset must be >= 1")

    df = daily_df.copy().reset_index(drop=True)
    if "symbol" not in df.columns or "timestamp" not in df.columns:
        raise ValueError("daily_df missing required columns: symbol, timestamp")
    for col in ("close", "volume"):
        if col not in df.columns:
            raise ValueError(f"daily_df missing required column: {col}")

    normalized_symbol = str(symbol).strip().upper()
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["session_date"] = _as_market_date_series(df["timestamp"], session_timezone)
    sym_df = df[df["symbol"] == normalized_symbol].sort_values("timestamp").reset_index(drop=True)
    if sym_df.empty:
        raise ValueError(f"symbol not found in daily_df: {normalized_symbol}")

    breakout_date_norm = pd.Timestamp(breakout_date).date().isoformat()
    breakout_idx = sym_df.index[sym_df["session_date"] == breakout_date_norm].tolist()
    if not breakout_idx:
        raise ValueError(f"breakout_date not found for {normalized_symbol}: {breakout_date_norm}")
    idx = int(breakout_idx[0])
    if idx == 0:
        raise ValueError("breakout_date requires a previous trading day")
    if idx < pre_window:
        raise ValueError(
            f"not enough pre-window history for {normalized_symbol} at {breakout_date_norm}: "
            f"need {pre_window}, have {idx}"
        )

    previous_idx = idx - 1
    previous_row = sym_df.iloc[previous_idx]
    breakout_row = sym_df.iloc[idx]

    confirm_idx = idx + confirm_offset
    confirm_row = sym_df.iloc[confirm_idx] if confirm_idx < len(sym_df) else None
    confirm_date = None if confirm_row is None else str(confirm_row["session_date"])

    pre_window_df = sym_df.iloc[idx - pre_window : idx].reset_index(drop=True)

    breakout_open = float(breakout_row["open"]) if "open" in breakout_row else float("nan")
    breakout_close = float(breakout_row["close"])
    confirm_close = float("nan") if confirm_row is None else float(confirm_row["close"])

    return {
        "symbol": normalized_symbol,
        "breakout_date": breakout_date_norm,
        "previous_date": str(previous_row["session_date"]),
        "confirm_date": confirm_date,
        "pre_window": int(pre_window),
        "confirm_offset": int(confirm_offset),
        "trim_top_n": int(trim_top_n),
        "trim_bottom_n": int(trim_bottom_n),
        "price_lr_raw": compute_window_lr(pre_window_df["close"], pre_window),
        "price_lr_trimmed": compute_trimmed_window_lr(
            pre_window_df["close"],
            pre_window,
            trim_top_n=trim_top_n,
            trim_bottom_n=trim_bottom_n,
        ),
        "vol_lr_raw": compute_window_lr(pre_window_df["volume"], pre_window),
        "vol_lr_trimmed": compute_trimmed_window_lr(
            pre_window_df["volume"],
            pre_window,
            trim_top_n=trim_top_n,
            trim_bottom_n=trim_bottom_n,
        ),
        "breakout_green": breakout_close > breakout_open,
        "breakout_close_position_in_range": compute_close_position_in_range(
            open_price=breakout_open,
            high_price=float(breakout_row["high"]),
            low_price=float(breakout_row["low"]),
            close_price=breakout_close,
        ),
        "confirm_close_vs_breakout_close": (
            float("nan")
            if confirm_row is None
            else compute_ratio(confirm_close, breakout_close)
        ),
        "confirm_close_position_in_range": (
            float("nan")
            if confirm_row is None
            else compute_close_position_in_range(
                open_price=float(confirm_row["open"]),
                high_price=float(confirm_row["high"]),
                low_price=float(confirm_row["low"]),
                close_price=confirm_close,
            )
        ),
        "confirm_vol_vs_breakout_vol": (
            float("nan")
            if confirm_row is None
            else compute_ratio(float(confirm_row["volume"]), float(breakout_row["volume"]))
        ),
        "pre_max_drawdown": compute_max_drawdown(pre_window_df["close"]),
        "pre_gap_down_count": int(pre_window_df["close"].pct_change().lt(-0.08).sum()),
        "price_ratio_prev_to_breakout": compute_ratio(
            breakout_close,
            float(previous_row["close"]),
        ),
        "volume_ratio_prev_to_breakout": compute_ratio(
            float(breakout_row["volume"]),
            float(previous_row["volume"]),
        ),
        "price_ratio_prev_to_confirm": (
            float("nan")
            if confirm_row is None
            else compute_ratio(float(confirm_row["close"]), float(previous_row["close"]))
        ),
        "volume_ratio_prev_to_confirm": (
            float("nan")
            if confirm_row is None
            else compute_ratio(float(confirm_row["volume"]), float(previous_row["volume"]))
        ),
    }


__all__ = [
    "build_impulse_features",
    "compute_max_drawdown",
    "compute_close_position_in_range",
    "compute_ratio",
    "compute_trimmed_window_lr",
    "compute_window_lr",
]
