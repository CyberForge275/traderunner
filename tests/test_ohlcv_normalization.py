"""
Unit tests for OHLCV normalization with duplicate column handling.

Tests the defensive normalization logic that merges uppercase/lowercase OHLCV columns.
"""

import pytest
import pandas as pd
import numpy as np
from axiom_bt.intraday import _normalize_ohlcv_frame


def test_normalize_handles_duplicate_open_columns():
    """Test that duplicate Open/open columns are merged correctly."""
    # Create DF with both Open (uppercase) and open (lowercase)
    # Open has data in first row, open has data in second row
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-12-17 10:00', periods=3, freq='5min', tz='UTC'),
        'Open': [100.0, np.nan, np.nan],
        'open': [np.nan, 101.0, 102.0],
        'High': [105.0, 106.0, 107.0],
        'Low': [95.0, 96.0, 97.0],
        'Close': [103.0, 104.0, 105.0],
        'Volume': [1000, 2000, 3000]
    })
    
    result = _normalize_ohlcv_frame(df, target_tz='America/New_York', symbol='TEST')
    
    # Should have only lowercase columns
    assert list(result.columns) == ['open', 'high', 'low', 'close', 'volume']
    
    # Should have merged data from both Open and open
    assert result['open'].iloc[0] == 100.0  # From Open
    assert result['open'].iloc[1] == 101.0  # From open
    assert result['open'].iloc[2] == 102.0  # From open
    
    # Metadata should indicate duplicates were found
    assert result.attrs.get('ohlcv_had_duplicates') == True


def test_normalize_handles_all_duplicate_columns():
    """Test normalization with all OHLCV columns duplicated."""
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-12-17 10:00', periods=2, freq='5min', tz='UTC'),
        # Uppercase variants
        'Open': [100.0, np.nan],
        'High': [105.0, np.nan],
        'Low': [95.0, np.nan],
        'Close': [103.0, np.nan],
        'Volume': [1000.0, np.nan],
        # Lowercase variants
        'open': [np.nan, 101.0],
        'high': [np.nan, 106.0],
        'low': [np.nan, 96.0],
        'close': [np.nan, 104.0],
        'volume': [np.nan, 2000.0],
    })
    
    result = _normalize_ohlcv_frame(df, target_tz='America/New_York', symbol='DUPES')
    
    # All columns should be lowercase
    assert set(result.columns) == {'open', 'high', 'low', 'close', 'volume'}
    
    # Data should be merged correctly
    assert result['open'].iloc[0] == 100.0
    assert result['open'].iloc[1] == 101.0
    assert result['high'].iloc[0] == 105.0
    assert result['high'].iloc[1] == 106.0
    
    # Should have 5 merge operations logged in metadata
    assert result.attrs.get('ohlcv_had_duplicates') == True


def test_normalize_lowercase_only_no_duplicates():
    """Test that lowercase-only data passes through correctly."""
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-12-17 10:00', periods=2, freq='5min', tz='UTC'),
        'open': [100.0, 101.0],
        'high': [105.0, 106.0],
        'low': [95.0, 96.0],
        'close': [103.0, 104.0],
        'volume': [1000, 2000]
    })
    
    result = _normalize_ohlcv_frame(df, target_tz='America/New_York', symbol='CLEAN')
    
    assert list(result.columns) == ['open', 'high', 'low', 'close', 'volume']
    assert result.attrs.get('ohlcv_had_duplicates') == False
    assert result['open'].iloc[0] == 100.0
    assert result['open'].iloc[1] == 101.0


def test_normalize_uppercase_only_gets_renamed():
    """Test that uppercase-only columns get renamed to lowercase."""
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-12-17 10:00', periods=2, freq='5min', tz='UTC'),
        'Open': [100.0, 101.0],
        'High': [105.0, 106.0],
        'Low': [95.0, 96.0],
        'Close': [103.0, 104.0],
        'Volume': [1000, 2000]
    })
    
    result = _normalize_ohlcv_frame(df, target_tz='America/New_York', symbol='UPPER')
    
    # Should have lowercase columns
    assert list(result.columns) == ['open', 'high', 'low', 'close', 'volume']
    
    # Data should be preserved
    assert result['open'].iloc[0] == 100.0
    assert result['close'].iloc[1] == 104.0
    
    # No duplicates since only uppercase existed
    assert result.attrs.get('ohlcv_had_duplicates') == False


def test_normalize_preserves_timezone():
    """Test that timezone conversion works correctly."""
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-12-17 14:30', periods=1, freq='5min', tz='UTC'),
        'open': [100.0],
        'high': [105.0],
        'low': [95.0],
        'close': [103.0],
        'volume': [1000]
    })
    
    result = _normalize_ohlcv_frame(df, target_tz='America/New_York', symbol='TZ_TEST')
    
    # Index should be timezone-aware
    assert result.index.tz is not None
    assert str(result.index.tz) == 'America/New_York'
    
    # 14:30 UTC = 09:30 EST (winter) or 10:30 EDT (summer)
    # Just verify it's in NY timezone
    ny_time = result.index[0]
    assert ny_time.hour in [9, 10]  # Depending on DST


def test_normalize_calculates_nan_stats():
    """Test that NaN statistics are calculated and attached."""
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-12-17 10:00', periods=4, freq='5min', tz='UTC'),
        'open': [100.0, np.nan, 102.0, 103.0],
        'high': [105.0, 106.0, np.nan, 108.0],
        'low': [95.0, 96.0, 97.0, 98.0],
        'close': [103.0, 104.0, 105.0, np.nan],
        'volume': [1000, 2000, 3000, 4000]
    })
    
    result = _normalize_ohlcv_frame(df, target_tz='America/New_York', symbol='NAN_TEST')
    
    # Check NaN stats in metadata
    nan_stats = result.attrs.get('ohlcv_nan_stats', {})
    
    assert nan_stats['open']['count'] == 1
    assert nan_stats['open']['pct'] == 25.0
    
    assert nan_stats['high']['count'] == 1
    assert nan_stats['high']['pct'] == 25.0
    
    assert nan_stats['low']['count'] == 0
    assert nan_stats['low']['pct'] == 0.0
    
    assert nan_stats['close']['count'] == 1
    assert nan_stats['close']['pct'] == 25.0


if __name__ == "__main__":
    # Run tests
    test_normalize_handles_duplicate_open_columns()
    print("✓ test_normalize_handles_duplicate_open_columns PASSED")
    
    test_normalize_handles_all_duplicate_columns()
    print("✓ test_normalize_handles_all_duplicate_columns PASSED")
    
    test_normalize_lowercase_only_no_duplicates()
    print("✓ test_normalize_lowercase_only_no_duplicates PASSED")
    
    test_normalize_uppercase_only_gets_renamed()
    print("✓ test_normalize_uppercase_only_gets_renamed PASSED")
    
    test_normalize_preserves_timezone()
    print("✓ test_normalize_preserves_timezone PASSED")
    
    test_normalize_calculates_nan_stats()
    print("✓ test_normalize_calculates_nan_stats PASSED")
    
    print("\nAll OHLCV normalization tests PASSED!")
