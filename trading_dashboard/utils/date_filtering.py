"""
Date filtering utilities for backtesting charts.

Handles:
- D1 window-based filtering (1M/3M/6M/12M/All)
- Effective date calculation (clamping, trading day rollback)
- Intraday exact-day filtering
"""

import pandas as pd
from datetime import date, datetime
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Window mapping: label -> trading days
WINDOW_BARS = {
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "12M": 252,
    "All": None,
}


def calculate_effective_date(
    requested_date: Optional[date],
    df: pd.DataFrame,
) -> Tuple[pd.Timestamp, str]:
    """
    Calculate effective date for chart display with clamping and rollback.

    Rules:
    1. If requested_date > max available -> clamp to max
    2. If requested_date < min available -> clamp to min
    3. If requested_date is weekend/holiday -> roll back to last trading day
    4. If requested_date is None -> use max available

    Args:
        requested_date: Date from picker (None = use latest)
        df: DataFrame with DatetimeIndex (must have data)

    Returns:
        Tuple of (effective_date as Timestamp, reason string)

    Raises:
        ValueError: If df is empty or has no DatetimeIndex
    """
    if df.empty:
        raise ValueError("Cannot calculate effective date from empty DataFrame")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"DataFrame index must be DatetimeIndex, got {type(df.index)}")

    min_date = df.index.min()
    max_date = df.index.max()

    # Default: use latest available
    if requested_date is None:
        return max_date, "default_latest"

    # Convert to timestamp for comparison
    requested_ts = pd.Timestamp(requested_date, tz=df.index.tz)

    # Clamp to available range
    if requested_ts > max_date:
        logger.info(
            f"Requested date {requested_date} beyond max {max_date.date()}, "
            "clamping to max"
        )
        return max_date, "clamped_max"

    if requested_ts < min_date:
        logger.info(
            f"Requested date {requested_date} before min {min_date.date()}, "
            "clamping to min"
        )
        return min_date, "clamped_min"

    # Roll back to last trading day if weekend/holiday
    # Find closest date <= requested_date
    dates_up_to_requested = df.index[df.index.normalize() <= requested_ts.normalize()]

    if len(dates_up_to_requested) == 0:
        # Shouldn't happen given min_date check, but defensively use min
        return min_date, "rolled_back_to_min"

    effective_date = dates_up_to_requested.max()

    if effective_date.date() != requested_date:
        logger.info(
            f"Requested date {requested_date} not a trading day, "
            f"rolled back to {effective_date.date()}"
        )
        return effective_date, "rolled_back"

    return effective_date, "exact_match"


def apply_d1_window(
    df: pd.DataFrame,
    effective_date: pd.Timestamp,
    window: str = "12M",
) -> pd.DataFrame:
    """
    Apply window-based filtering for D1 (daily) data.

    Window logic:
    - 1M/3M/6M/12M: Show N trading days ending at effective_date
    - All: Show all data up to effective_date

    Args:
        df: Daily OHLCV DataFrame (DatetimeIndex)
        effective_date: End date for window
        window: Window size ("1M", "3M", "6M", "12M", "All")

    Returns:
        Filtered DataFrame

    Raises:
        ValueError: If window not recognized
    """
    if window not in WINDOW_BARS:
        raise ValueError(
            f"Invalid window '{window}'. Must be one of: {list(WINDOW_BARS.keys())}"
        )

    # Slice up to effective_date
    df_sliced = df.loc[:effective_date]

    # Apply window (tail N bars)
    window_bars = WINDOW_BARS[window]
    if window_bars is not None:
        df_sliced = df_sliced.tail(window_bars)
        logger.debug(
            f"Applied {window} window ({window_bars} bars), "
            f"resulting in {len(df_sliced)} rows"
        )
    else:
        logger.debug(f"Window=All, showing all data up to {effective_date.date()}")

    return df_sliced


def apply_intraday_exact_day(
    df: pd.DataFrame,
    effective_date: pd.Timestamp,
    market_tz: str = "America/New_York",
) -> pd.DataFrame:
    """
    Filter intraday data to exact trading day in market timezone.

    STRICT filtering: only bars where date(tz=market_tz) == effective_date

    Args:
        df: Intraday OHLCV DataFrame (DatetimeIndex, tz-aware)
        effective_date: Trading day to filter to
        market_tz: Market timezone (must match df timezone)

    Returns:
        Filtered DataFrame (may be empty if no data for day)
    """
    if df.empty:
        return df

    # Ensure timezone
    if df.index.tz is None:
        logger.warning(f"DataFrame has no timezone, localizing to {market_tz}")
        df = df.tz_localize(market_tz)
    elif str(df.index.tz) != market_tz:
        logger.debug(f"Converting from {df.index.tz} to {market_tz}")
        df = df.tz_convert(market_tz)

    # Get target date (normalized to date component)
    target_date = effective_date.date()

    # Filter to exact day
    mask = df.index.date == target_date
    df_filtered = df[mask]

    logger.debug(
        f"Intraday exact-day filter: {len(df)} rows -> {len(df_filtered)} rows "
        f"for date {target_date}"
    )

    return df_filtered
