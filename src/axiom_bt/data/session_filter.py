"""
Session filtering utilities for intraday data.

Provides functions to filter raw market data to specific trading sessions,
such as Regular Trading Hours (RTH) only, excluding Pre-Market and After-Hours.
"""

from __future__ import annotations

import logging
from datetime import time

import pandas as pd

logger = logging.getLogger(__name__)


def filter_rth_session(
    df: pd.DataFrame,
    tz: str = "America/New_York",
    rth_start: str = "09:30",
    rth_end: str = "16:00",
) -> pd.DataFrame:
    """
    Filter DataFrame to Regular Trading Hours (RTH) only.

    US Market RTH is typically 09:30-16:00 Eastern Time. This function
    removes Pre-Market (04:00-09:30) and After-Hours (16:00-20:00) data.

    Args:
        df: DataFrame with DatetimeIndex or 'timestamp' column (UTC or timezone-aware)
        tz: Target timezone for session filtering (default: America/New_York)
        rth_start: RTH start time in HH:MM format (default: 09:30)
        rth_end: RTH end time in HH:MM format (default: 16:00)

    Returns:
        Filtered DataFrame containing only RTH data

    Raises:
        ValueError: If DataFrame has no timestamp index or column

    Example:
        >>> # Filter 24h data to RTH only
        >>> df_all = pd.read_parquet("TSLA_raw.parquet")  # All hours
        >>> df_rth = filter_rth_session(df_all)  # 09:30-16:00 only
        >>>
        >>> # Custom session hours
        >>> df_custom = filter_rth_session(df, rth_start="10:00", rth_end="15:30")

    Notes:
        - Input timestamps are converted to target timezone before filtering
        - UTC timestamps (EODHD format) are properly handled
        - Naive timestamps are assumed to be UTC
        - Output retains original timezone of input
    """
    # Get timestamp series in target timezone
    if "timestamp" in df.columns:
        # Column-based timestamp
        ts_series = pd.to_datetime(df["timestamp"], errors="coerce")

        # Ensure timezone-aware (assume UTC if naive)
        if ts_series.dt.tz is None:
            ts_series = ts_series.dt.tz_localize("UTC")

        # Convert to target timezone
        ts_tz = ts_series.dt.tz_convert(tz)

    elif isinstance(df.index, pd.DatetimeIndex):
        # Index-based timestamp
        ts_series = df.index

        # Ensure timezone-aware (assume UTC if naive)
        if ts_series.tz is None:
            ts_series = pd.to_datetime(ts_series, utc=True)

        # Convert to target timezone
        ts_tz = ts_series.tz_convert(tz)

    else:
        raise ValueError(
            "DataFrame must have DatetimeIndex or 'timestamp' column. "
            f"Got index type: {type(df.index)}"
        )

    # Parse session boundary times
    start_time = pd.Timestamp(rth_start).time()
    end_time = pd.Timestamp(rth_end).time()

    # Create mask for RTH hours
    # Note: end_time is EXCLUSIVE (< not <=) to match standard convention
    mask = (ts_tz.time >= start_time) & (ts_tz.time < end_time)

    # Filter and return
    df_filtered = df[mask].copy()

    # Log filtering stats
    rows_before = len(df)
    rows_after = len(df_filtered)
    rows_removed = rows_before - rows_after
    percentage_kept = (rows_after / rows_before * 100) if rows_before > 0 else 0

    logger.info(
        f"RTH filter: {rows_before:,} → {rows_after:,} rows "
        f"({percentage_kept:.1f}% kept, {rows_removed:,} removed)"
    )

    if rows_after == 0:
        logger.warning(
            f"RTH filter removed ALL data! Check session hours ({rth_start}-{rth_end}) "
            f"and timezone ({tz})"
        )

    return df_filtered


def get_rth_stats(
    df: pd.DataFrame,
    tz: str = "America/New_York",
) -> dict:
    """
    Get statistics about RTH vs Pre/After-Market data distribution.

    Args:
        df: DataFrame with timestamp data
        tz: Timezone for session analysis

    Returns:
        Dict with keys:
            - total_rows: Total number of rows
            - rth_rows: Rows during RTH (09:30-16:00)
            - pre_market_rows: Rows during Pre-Market (04:00-09:30)
            - after_hours_rows: Rows during After-Hours (16:00-20:00)
            - other_rows: Rows outside standard session hours
            - rth_percentage: Percentage of data in RTH

    Example:
        >>> stats = get_rth_stats(df)
        >>> print(f"RTH: {stats['rth_percentage']:.1f}%")
        RTH: 28.3%
    """
    # Get timezone-localized timestamps
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        ts = ts.dt.tz_convert(tz)
    else:
        ts = df.index
        if ts.tz is None:
            ts = pd.to_datetime(ts, utc=True)
        ts = ts.tz_convert(tz)

    # Define session boundaries
    pre_market_start = time(4, 0)
    rth_start = time(9, 30)
    rth_end = time(16, 0)
    after_hours_end = time(20, 0)

    # Count rows in each session
    total = len(df)

    times = ts.time
    pre_market = ((times >= pre_market_start) & (times < rth_start)).sum()
    rth = ((times >= rth_start) & (times < rth_end)).sum()
    after_hours = ((times >= rth_end) & (times < after_hours_end)).sum()
    other = total - pre_market - rth - after_hours

    return {
        "total_rows": total,
        "rth_rows": rth,
        "pre_market_rows": pre_market,
        "after_hours_rows": after_hours,
        "other_rows": other,
        "rth_percentage": (rth / total * 100) if total > 0 else 0,
    }
