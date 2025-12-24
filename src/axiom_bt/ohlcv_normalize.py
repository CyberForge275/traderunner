"""
OHLCV Normalization - Single Source of Truth

This module provides defensive normalization for OHLCV data at data loading boundaries.
Ensures lowercase-only columns and merges any duplicate uppercase/lowercase variants.

Design:
- Applied ONCE at data ingestion (parquet load, API fetch)
- Merges duplicate columns (Open+open → open) using "non-NaN wins" strategy
- Logs normalization events for debugging
- Enforces data contract: only open,high,low,close,volume allowed

Author: traderunner team
Date: 2025-12-19
"""

import pandas as pd
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Canonical OHLCV columns (lowercase only)
CANONICAL_OHLCV = ['open', 'high', 'low', 'close', 'volume']


def normalize_ohlcv_frame(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    source: str = "unknown",
    fail_on_nan: bool = True
) -> pd.DataFrame:
    """
    Normalize OHLCV DataFrame to lowercase-only canonical format.

    Applied at data boundaries (parquet load, API fetch) to ensure consistent
    column naming regardless of source data format.

    Normalization steps:
    1. Identify duplicate OHLCV columns (uppercase vs lowercase)
    2. Merge duplicates using "non-NaN wins" strategy
    3. Keep only lowercase variants
    4. Validate OHLC columns for NaN (optional fail-fast)
    5. Ensure float64 dtype and sorted index

    Args:
        df: Input DataFrame with potential mixed-case OHLCV columns
        symbol: Symbol name for logging
        source: Data source identifier for logging
        fail_on_nan: If True, raise ValueError on NaN in OHLC columns

    Returns:
        Normalized DataFrame with only lowercase OHLCV columns

    Raises:
        ValueError: If fail_on_nan=True and NaN found in OHLC columns

    Example:
        >>> df_raw = pd.DataFrame({
        ...     'Open': [100.0, np.nan],
        ...     'open': [np.nan, 101.0],
        ...     'High': [102.0, 103.0]
        ... })
        >>> df_norm = normalize_ohlcv_frame(df_raw, symbol='TEST')
        >>> list(df_norm.columns)
        ['open', 'high', 'low', 'close', 'volume']  # lowercase only
    """
    if df.empty:
        logger.debug(f"[{symbol}] Empty DataFrame, skipping normalization")
        return df

    original_columns = list(df.columns)
    had_duplicates = False
    merge_log = []

    # Step 1: Detect and merge duplicate OHLCV columns
    for canonical in CANONICAL_OHLCV:
        upper = canonical.capitalize()  # 'Open', 'High', etc.
        lower = canonical  # 'open', 'high', etc.

        has_upper = upper in df.columns
        has_lower = lower in df.columns

        if has_upper and has_lower:
            # Duplicate detected - merge with "non-NaN wins"
            had_duplicates = True

            # Count non-NaN in each variant
            upper_count = df[upper].notna().sum()
            lower_count = df[lower].notna().sum()

            # Merge strategy: combine_first prefers left (non-NaN)
            # We'll use the variant with more data as base
            if upper_count >= lower_count:
                df[lower] = df[upper].combine_first(df[lower])
                merge_log.append(f"{upper}({upper_count})+{lower}({lower_count})→{lower}")
            else:
                df[lower] = df[lower].combine_first(df[upper])
                merge_log.append(f"{lower}({lower_count})+{upper}({upper_count})→{lower}")

            # Drop uppercase variant
            df = df.drop(columns=[upper])

        elif has_upper and not has_lower:
            # Only uppercase exists - rename to lowercase
            df = df.rename(columns={upper: lower})
            merge_log.append(f"{upper}→{lower}")

    # Step 2: Ensure all canonical columns exist (fill with NaN if missing)
    for col in CANONICAL_OHLCV:
        if col not in df.columns:
            df[col] = pd.NaT if col == 'timestamp' else float('nan')

    # Step 3: Keep only canonical columns (+ timestamp/index if present)
    keep_cols = [c for c in df.columns if c in CANONICAL_OHLCV or c == 'timestamp']
    df = df[keep_cols]

    # Step 4: Ensure float64 dtype for OHLCV
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')

    # Step 5: Calculate NaN statistics
    nan_stats = {}
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            nan_count = df[col].isna().sum()
            nan_pct = (nan_count / len(df) * 100) if len(df) > 0 else 0
            nan_stats[col] = {'count': nan_count, 'pct': nan_pct}

    # Step 6: Sort index if datetime
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.sort_index()
    elif 'timestamp' in df.columns:
        df = df.sort_values('timestamp')

    # DEBUG LOGGING
    logger.debug(
        f"[OHLCV_NORMALIZE] symbol={symbol} source={source} "
        f"rows={len(df)} "
        f"columns_before={original_columns} "
        f"columns_after={list(df.columns)} "
        f"had_duplicates={had_duplicates}"
    )

    if merge_log:
        logger.info(
            f"[OHLCV_NORMALIZE] {symbol}: Merged duplicate columns: {', '.join(merge_log)}"
        )

    if nan_stats:
        nan_summary = ", ".join([f"{k}={v['count']}({v['pct']:.1f}%)" for k, v in nan_stats.items()])
        logger.debug(f"[OHLCV_NORMALIZE] {symbol}: NaN stats: {nan_summary}")

    # Step 7: Fail-fast on NaN in OHLC if requested
    if fail_on_nan:
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns and df[col].isna().any():
                nan_count = df[col].isna().sum()
                raise ValueError(
                    f"[OHLCV_NORMALIZE] {symbol}: Column '{col}' contains {nan_count} NaN values "
                    f"({nan_count/len(df)*100:.1f}%) - fail_on_nan=True"
                )

    return df


def get_normalization_report(df: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict[str, Any]:
    """
    Generate diagnostic report for OHLCV normalization.

    Useful for debugging data quality issues without modifying the DataFrame.

    Returns:
        Dict with keys: has_duplicates, duplicate_pairs, missing_columns, nan_stats
    """
    report = {
        'symbol': symbol,
        'total_rows': len(df),
        'has_duplicates': False,
        'duplicate_pairs': [],
        'missing_columns': [],
        'nan_stats': {},
        'columns': list(df.columns)
    }

    # Check for duplicate OHLCV columns
    for canonical in CANONICAL_OHLCV:
        upper = canonical.capitalize()
        lower = canonical

        if upper in df.columns and lower in df.columns:
            report['has_duplicates'] = True
            report['duplicate_pairs'].append((upper, lower))

    # Check for missing canonical columns
    for col in CANONICAL_OHLCV:
        if col not in df.columns:
            report['missing_columns'].append(col)

    # NaN statistics
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            nan_count = df[col].isna().sum()
            nan_pct = (nan_count / len(df) * 100) if len(df) > 0 else 0
            report['nan_stats'][col] = {'count': nan_count, 'pct': nan_pct}

    return report
