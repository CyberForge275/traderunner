"""
Chart Data Preprocessing - Shared Transformation Pipeline
==========================================================

CRITICAL: This module provides deterministic, testable transformations
for chart data used by BOTH Live and Backtesting tabs.

FORBIDDEN IMPORTS (Architecture constraint):
- sqlite3
- pandas.read_parquet
- axiom_bt.* / IntradayStore
- Any references to artifacts/data_* paths

This helper is DATA-SOURCE AGNOSTIC. It receives DataFrames and
transforms them according to timezone/filtering rules.
"""

import pandas as pd
from datetime import date, datetime
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

MARKET_TZ = "America/New_York"
DEFAULT_DISPLAY_TZ = "America/New_York"


# ==============================================================================
# CORE TRANSFORMATION FUNCTIONS
# ==============================================================================

def ensure_datetime_index(
    df: pd.DataFrame,
    ts_col: Optional[str] = None
) -> pd.DataFrame:
    """
    Ensure DataFrame has DatetimeIndex.
    
    Args:
        df: Input DataFrame
        ts_col: If index is not DatetimeIndex, use this column
        
    Returns:
        DataFrame with DatetimeIndex
        
    Raises:
        ValueError: If no DatetimeIndex and no ts_col provided
    """
    if isinstance(df.index, pd.DatetimeIndex):
        return df
    
    if ts_col is None:
        raise ValueError(
            "DataFrame does not have DatetimeIndex and no ts_col provided"
        )
    
    if ts_col not in df.columns:
        raise ValueError(f"Column '{ts_col}' not found in DataFrame")
    
    df = df.copy()
    df.index = pd.to_datetime(df[ts_col])
    df.index.name = 'timestamp'
    
    return df


def ensure_tz(
    df: pd.DataFrame,
    market_tz: str = MARKET_TZ
) -> pd.DataFrame:
    """
    Ensure DataFrame index is tz-aware in market timezone.
    
    Rules:
    - If tz-naive: localize to market_tz
    - If tz-aware: convert to market_tz
    
    Args:
        df: DataFrame with DatetimeIndex
        market_tz: Target timezone (default: America/New_York)
        
    Returns:
        DataFrame with tz-aware index in market_tz
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Index must be DatetimeIndex")
    
    df = df.copy()
    
    if df.index.tz is None:
        # Naive: localize (assume data is in market TZ)
        df.index = df.index.tz_localize(market_tz)
        logger.debug(f"Localized naive index to {market_tz}")
    else:
        # Already tz-aware: convert
        df.index = df.index.tz_convert(market_tz)
        logger.debug(f"Converted index to {market_tz}")
    
    return df


def drop_invalid_ohlc(
    df: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict]:
    """
    Drop rows where OHLC values are NaN.
    
    Args:
        df: DataFrame with OHLC columns
        
    Returns:
        Tuple of (clean_df, stats)
        stats contains: rows_before, rows_after, dropped_rows
    """
    rows_before = len(df)
    
    # Check which OHLC columns exist
    ohlc_cols = []
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            ohlc_cols.append(col)
    
    if not ohlc_cols:
        # No OHLC columns to check
        return df, {
            'rows_before': rows_before,
            'rows_after': rows_before,
            'dropped_rows': 0
        }
    
    # Drop rows where ANY OHLC is NaN
    df_clean = df.dropna(subset=ohlc_cols)
    rows_after = len(df_clean)
    dropped_rows = rows_before - rows_after
    
    if dropped_rows > 0:
        logger.debug(f"Dropped {dropped_rows} rows with NaN OHLC values")
    
    return df_clean, {
        'rows_before': rows_before,
        'rows_after': rows_after,
        'dropped_rows': dropped_rows
    }


def apply_date_filter_market(
    df: pd.DataFrame,
    ref_date: Optional[date],
    market_tz: str = MARKET_TZ
) -> Tuple[pd.DataFrame, Dict]:
    """
    Apply date filtering in market timezone (ONLY for past dates).
    
    Rules:
    - ref_date is None: No filtering
    - ref_date >= today (in market_tz): No filtering
    - ref_date < today: Filter to that specific date
    
    Args:
        df: DataFrame with tz-aware DatetimeIndex in market_tz
        ref_date: Reference date for filtering (or None)
        market_tz: Market timezone for "today" calculation
        
    Returns:
        Tuple of (filtered_df, stats)
        stats contains: date_filter_applied bool, ref_date
    """
    stats = {
        'date_filter_applied': False,
        'ref_date': ref_date
    }
    
    if ref_date is None:
        return df, stats
    
    # Calculate "today" in market timezone
    now_market = pd.Timestamp.now(tz=market_tz)
    today_market = now_market.date()
    
    if ref_date >= today_market:
        # Don't filter current or future dates
        logger.debug(f"Date filter skipped: {ref_date} >= {today_market} (today)")
        return df, stats
    
    # Filter to specific historical date
    df_filtered = df[df.index.date == ref_date]
    stats['date_filter_applied'] = True
    
    logger.info(f"📅 Date filtered to {ref_date}: {len(df)} → {len(df_filtered)} rows")
    
    return df_filtered, stats


def convert_display_tz(
    df: pd.DataFrame,
    display_tz: str = DEFAULT_DISPLAY_TZ
) -> pd.DataFrame:
    """
    Convert index timezone for display (MUST NOT change row count).
    
    CRITICAL: This is DISPLAY ONLY. No filtering allowed.
    
    Args:
        df: DataFrame with tz-aware DatetimeIndex
        display_tz: Target display timezone
        
    Returns:
        DataFrame with index in display_tz
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Index must be DatetimeIndex")
    
    if df.index.tz is None:
        raise ValueError("Index must be tz-aware before display conversion")
    
    df = df.copy()
    df.index = df.index.tz_convert(display_tz)
    
    logger.debug(f"Converted display timezone to {display_tz}")
    
    return df


def assert_rowcount_invariant(
    df_before: pd.DataFrame,
    df_after: pd.DataFrame,
    context: str
) -> None:
    """
    Assert that row count hasn't changed (critical for TZ conversion).
    
    Args:
        df_before: DataFrame before operation
        df_after: DataFrame after operation
        context: Description of operation (for error message)
        
    Raises:
        AssertionError: If row counts differ
    """
    rows_before = len(df_before)
    rows_after = len(df_after)
    
    assert rows_before == rows_after, (
        f"Row count changed during {context}! "
        f"Before: {rows_before}, After: {rows_after}. "
        f"This violates timezone invariance constraint."
    )
    
    logger.debug(f"✓ Row count invariant OK for {context}: {rows_before} rows")


# ==============================================================================
# ORCHESTRATOR
# ==============================================================================

def preprocess_for_chart(
    df: pd.DataFrame,
    *,
    source: str,  # "LIVE_SQLITE" | "BACKTEST_PARQUET"
    ref_date: Optional[date],
    display_tz: str,
    market_tz: str = MARKET_TZ,
    ts_col: Optional[str] = None
) -> Tuple[pd.DataFrame, Dict]:
    """
    Complete preprocessing pipeline for chart data.
    
    Pipeline (deterministic order):
    1. Ensure DatetimeIndex
    2. Ensure market timezone
    3. Drop invalid OHLC rows
    4. Apply date filtering (market TZ, only for past dates)
    5. Convert to display timezone
    6. Assert rowcount invariant (step 4→5)
    
    Args:
        df: Input DataFrame
        source: Data source identifier ("LIVE_SQLITE" or "BACKTEST_PARQUET")
        ref_date: Reference date for filtering (None = no filter)
        display_tz: Display timezone
        market_tz: Market timezone (default: America/New_York)
        ts_col: Timestamp column name if index is not DatetimeIndex
        
    Returns:
        Tuple of (processed_df, metadata)
        
    Metadata contains:
        - source: str
        - rows_before: int (initial)
        - rows_after: int (final)
        - dropped_rows: int
        - date_filter_applied: bool
        - first_ts: pd.Timestamp | None
        - last_ts: pd.Timestamp | None
        - market_tz: str
        - display_tz: str
    """
    rows_initial = len(df)
    
    # === Step 1: Ensure DatetimeIndex ===
    df = ensure_datetime_index(df, ts_col=ts_col)
    
    # === Step 2: Ensure market timezone ===
    df = ensure_tz(df, market_tz=market_tz)
    
    # === Step 3: Drop invalid OHLC rows ===
    df, drop_stats = drop_invalid_ohlc(df)
    
    # === Step 4: Apply date filtering (market TZ) ===
    df_after_filter = df
    df, filter_stats = apply_date_filter_market(df, ref_date, market_tz)
    
    # === Step 5: Convert to display timezone ===
    df_display = convert_display_tz(df, display_tz)
    
    # === Step 6: Assert rowcount invariant (filter→display) ===
    # Row count CAN change during filter/drop, but MUST NOT change during TZ display conversion
    assert_rowcount_invariant(df, df_display, "timezone display conversion")
    
    # === Compute metadata ===
    first_ts = df_display.index[0] if len(df_display) > 0 else None
    last_ts = df_display.index[-1] if len(df_display) > 0 else None
    
    metadata = {
        'source': source,
        'rows_before': rows_initial,
        'rows_after': len(df_display),
        'dropped_rows': drop_stats['dropped_rows'],
        'date_filter_applied': filter_stats['date_filter_applied'],
        'first_ts': first_ts,
        'last_ts': last_ts,
        'market_tz': market_tz,
        'display_tz': display_tz,
    }
    
    logger.debug(
        f"Chart preprocessing complete: "
        f"source={source} rows={rows_initial}→{len(df_display)} "
        f"dropped={drop_stats['dropped_rows']} "
        f"date_filter={filter_stats['date_filter_applied']}"
    )
    
    return df_display, metadata
