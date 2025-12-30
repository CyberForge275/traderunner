"""
Unit Tests for Chart Preprocessing Helper
==========================================

Tests the deterministic transformation pipeline used by both
Live and Backtesting chart tabs.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from trading_dashboard.utils.chart_preprocess import (
    ensure_datetime_index,
    ensure_tz,
    drop_invalid_ohlc,
    apply_date_filter_market,
    convert_display_tz,
    assert_rowcount_invariant,
    preprocess_for_chart,
    MARKET_TZ,
)


# ==============================================================================
# TEST: ensure_datetime_index
# ==============================================================================

def test_ensure_datetime_index_already_has_index():
    """If DataFrame already has DatetimeIndex, return as-is."""
    timestamps = pd.date_range('2025-01-01', periods=10, freq='5min')
    df = pd.DataFrame({'close': range(10)}, index=timestamps)

    result = ensure_datetime_index(df)

    assert isinstance(result.index, pd.DatetimeIndex)
    assert len(result) == 10


def test_ensure_datetime_index_from_column():
    """Convert column to DatetimeIndex if specified."""
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-01-01', periods=10, freq='5min'),
        'close': range(10)
    })

    result = ensure_datetime_index(df, ts_col='timestamp')

    assert isinstance(result.index, pd.DatetimeIndex)
    assert len(result) == 10
    assert result.index.name == 'timestamp'


def test_ensure_datetime_index_raises_without_ts_col():
    """Raise ValueError if no DatetimeIndex and no ts_col."""
    df = pd.DataFrame({'close': range(10)})

    with pytest.raises(ValueError, match="no ts_col provided"):
        ensure_datetime_index(df)


# ==============================================================================
# TEST: ensure_tz
# ==============================================================================

def test_ensure_tz_localize_naive_index():
    """Naive DatetimeIndex should be localized to market_tz."""
    timestamps = pd.date_range('2025-01-01', periods=10, freq='5min')  # Naive
    df = pd.DataFrame({'close': range(10)}, index=timestamps)

    result = ensure_tz(df, market_tz=MARKET_TZ)

    assert result.index.tz is not None
    assert str(result.index.tz) == MARKET_TZ
    assert len(result) == 10


def test_ensure_tz_convert_aware_index():
    """Tz-aware index should be converted to market_tz."""
    timestamps = pd.date_range('2025-01-01', periods=10, freq='5min', tz='UTC')
    df = pd.DataFrame({'close': range(10)}, index=timestamps)

    result = ensure_tz(df, market_tz=MARKET_TZ)

    assert result.index.tz is not None
    assert str(result.index.tz) == MARKET_TZ
    assert len(result) == 10


# ==============================================================================
# TEST: drop_invalid_ohlc
# ==============================================================================

def test_drop_invalid_ohlc_drops_nan_rows():
    """Rows with NaN in OHLC should be dropped."""
    df = pd.DataFrame({
        'open': [1.0, np.nan, 3.0, 4.0, np.nan],
        'high': [2.0, 2.0, 4.0, 5.0, 5.0],
        'low': [0.5, 1.5, 2.5, 3.5, 4.5],
        'close': [1.5, 2.5, 3.5, 4.5, np.nan],
        'volume': [100, 200, 300, 400, 500]
    }, index=pd.date_range('2025-01-01', periods=5, freq='5min'))

    result, stats = drop_invalid_ohlc(df)

    assert stats['rows_before'] == 5
    assert stats['rows_after'] == 3  # Rows 0, 2, 3 remain (rows 1,4 have NaN)
    assert stats['dropped_rows'] == 2
    assert len(result) == 3


def test_drop_invalid_ohlc_no_drops_if_clean():
    """If no NaN rows, nothing should be dropped."""
    df = pd.DataFrame({
        'open': [1.0, 2.0, 3.0],
        'high': [2.0, 3.0, 4.0],
        'low': [0.5, 1.5, 2.5],
        'close': [1.5, 2.5, 3.5],
        'volume': [100, 200, 300]
    }, index=pd.date_range('2025-01-01', periods=3, freq='5min'))

    result, stats = drop_invalid_ohlc(df)

    assert stats['dropped_rows'] == 0
    assert len(result) == 3


# ==============================================================================
# TEST: apply_date_filter_market
# ==============================================================================

def test_apply_date_filter_only_for_past_dates_market_tz():
    """Date filter should only apply for ref_date < today."""
    timestamps = pd.date_range('2025-01-15 09:30', periods=10, freq='5min', tz=MARKET_TZ)
    df = pd.DataFrame({'close': range(10)}, index=timestamps)

    # Test 1: ref_date = None → no filter
    result, stats = apply_date_filter_market(df, ref_date=None, market_tz=MARKET_TZ)
    assert stats['date_filter_applied'] == False
    assert len(result) == 10

    # Test 2: ref_date = yesterday → filter applied
    yesterday = (pd.Timestamp.now(tz=MARKET_TZ) - timedelta(days=1)).date()
    df_past = df.copy()
    df_past.index = pd.date_range(
        f'{yesterday} 09:30', periods=10, freq='5min', tz=MARKET_TZ
    )
    result, stats = apply_date_filter_market(df_past, ref_date=yesterday, market_tz=MARKET_TZ)
    assert stats['date_filter_applied'] == True
    assert len(result) == 10  # All rows match yesterday

    # Test 3: ref_date = today → no filter (could be live data)
    today = pd.Timestamp.now(tz=MARKET_TZ).date()
    result, stats = apply_date_filter_market(df, ref_date=today, market_tz=MARKET_TZ)
    assert stats['date_filter_applied'] == False


# ==============================================================================
# TEST: convert_display_tz
# ==============================================================================

def test_convert_display_tz_invariant_rowcount():
    """Converting display timezone MUST NOT change row count."""
    timestamps = pd.date_range('2025-01-01 09:30', periods=100, freq='5min', tz=MARKET_TZ)
    df = pd.DataFrame({'close': range(100)}, index=timestamps)

    # Convert to Berlin time
    result = convert_display_tz(df, display_tz='Europe/Berlin')

    # CRITICAL: Row count must be identical
    assert len(result) == len(df)
    assert len(result) == 100

    # Timezone should be Berlin
    assert str(result.index.tz) == 'Europe/Berlin'


def test_convert_display_tz_back_and_forth_invariant():
    """Converting NY→Berlin→NY must preserve row count."""
    timestamps = pd.date_range('2025-01-01 09:30', periods=100, freq='5min', tz=MARKET_TZ)
    df_original = pd.DataFrame({'close': range(100)}, index=timestamps)

    # NY → Berlin
    df_berlin = convert_display_tz(df_original, display_tz='Europe/Berlin')
    assert len(df_berlin) == 100

    # Berlin → NY
    df_ny_again = convert_display_tz(df_berlin, display_tz=MARKET_TZ)
    assert len(df_ny_again) == 100

    # Row counts must all match
    assert len(df_original) == len(df_berlin) == len(df_ny_again)


# ==============================================================================
# TEST: assert_rowcount_invariant
# ==============================================================================

def test_assert_rowcount_invariant_passes():
    """Assertion should pass if row counts match."""
    df1 = pd.DataFrame({'a': range(10)})
    df2 = pd.DataFrame({'b': range(10)})

    # Should not raise
    assert_rowcount_invariant(df1, df2, "test operation")


def test_assert_rowcount_invariant_fails():
    """Assertion should fail if row counts differ."""
    df1 = pd.DataFrame({'a': range(10)})
    df2 = pd.DataFrame({'b': range(5)})

    with pytest.raises(AssertionError, match="Row count changed"):
        assert_rowcount_invariant(df1, df2, "test operation")


# ==============================================================================
# TEST: preprocess_for_chart (Integration)
# ==============================================================================

def test_preprocess_for_chart_meta_fields_present():
    """Metadata should contain all required fields."""
    timestamps = pd.date_range('2025-01-01 09:30', periods=50, freq='5min')
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': np.random.rand(50) + 100,
        'high': np.random.rand(50) + 101,
        'low': np.random.rand(50) + 99,
        'close': np.random.rand(50) + 100,
        'volume': np.random.randint(1000, 10000, 50)
    })

    result_df, meta = preprocess_for_chart(
        df,
        source="LIVE_SQLITE",
        ref_date=None,
        display_tz='Europe/Berlin',
        market_tz=MARKET_TZ,
        ts_col='timestamp'
    )

    # Check all required metadata fields
    assert meta['source'] == 'LIVE_SQLITE'
    assert 'rows_before' in meta
    assert 'rows_after' in meta
    assert 'dropped_rows' in meta
    assert 'date_filter_applied' in meta
    assert 'first_ts' in meta
    assert 'last_ts' in meta
    assert meta['market_tz'] == MARKET_TZ
    assert meta['display_tz'] == 'Europe/Berlin'


def test_preprocess_for_chart_no_row_loss_on_tz_conversion():
    """TZ conversion during preprocessing must not lose rows."""
    timestamps = pd.date_range('2025-01-01 09:30', periods=100, freq='5min')
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': range(100),
        'high': range(100),
        'low': range(100),
        'close': range(100),
        'volume': range(100)
    })

    result_df, meta = preprocess_for_chart(
        df,
        source="BACKTEST_PARQUET",
        ref_date=None,  # No date filter
        display_tz='Europe/Berlin',
        ts_col='timestamp'
    )

    # No rows should be lost (no NaN, no filter)
    assert len(result_df) == 100
    assert meta['rows_after'] == 100
    assert meta['dropped_rows'] == 0


def test_preprocess_for_chart_drops_nan_correctly():
    """NaN rows should be dropped and counted."""
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-01-01', periods=10, freq='5min'),
        'open': [1, np.nan, 3, 4, 5, np.nan, 7, 8, 9, 10],
        'high': [2, 2, 4, 5, 6, 6, 8, 9, 10, 11],
        'low': [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5],
        'close': [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5],
        'volume': range(10)
    })

    result_df, meta = preprocess_for_chart(
        df,
        source="LIVE_SQLITE",
        ref_date=None,
        display_tz=MARKET_TZ,
        ts_col='timestamp'
    )

    # 2 NaN rows should be dropped
    assert meta['dropped_rows'] == 2
    assert meta['rows_after'] == 8
    assert len(result_df) == 8
