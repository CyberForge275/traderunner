"""Tests for intraday data normalization."""

import numpy as np
import pandas as pd
import pytest

from axiom_bt.intraday import _normalize_ohlcv_frame


class TestNormalizeOHLCVFrame:
    """Tests for _normalize_ohlcv_frame function."""

    def test_duplicate_columns_prefers_capitalized(self):
        """When both Capitalized and lowercase columns exist, prefer Capitalized with data."""
        # Simulate EODHD parquet with duplicate columns
        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=5, freq='1min', tz='UTC'),
            # Capitalized columns (EODHD format) - WITH DATA
            'Open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'High': [100.5, 101.5, 102.5, 103.5, 104.5],
            'Low': [99.5, 100.5, 101.5, 102.5, 103.5],
            'Close': [100.2, 101.2, 102.2, 103.2, 104.2],
            'Volume': [1000, 2000, 3000, 4000, 5000],
            # lowercase columns - ALL NaN (corrupt/duplicate)
            'open': [np.nan] * 5,
            'high': [np.nan] * 5,
            'low': [np.nan] * 5,
            'close': [np.nan] * 5,
            'volume': [np.nan] * 5,
        })

        result = _normalize_ohlcv_frame(df, target_tz='America/New_York')

        # Should use Capitalized columns (with data), not lowercase (NaN)
        assert result['open'].notna().all(), "open column should have data, not NaN"
        assert result['high'].notna().all(), "high column should have data, not NaN"
        assert result['low'].notna().all(), "low column should have data, not NaN"
        assert result['close'].notna().all(), "close column should have data, not NaN"
        assert result['volume'].notna().all(), "volume column should have data, not NaN"

        # Verify actual values from Capitalized columns
        assert result['open'].iloc[0] == 100.0
        assert result['close'].iloc[-1] == 104.2
        assert result['volume'].iloc[2] == 3000

    def test_lowercase_only_columns_work(self):
        """When only lowercase columns exist, they should be used."""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=3, freq='1min', tz='UTC'),
            'open': [10.0, 11.0, 12.0],
            'high': [10.5, 11.5, 12.5],
            'low': [9.5, 10.5, 11.5],
            'close': [10.2, 11.2, 12.2],
            'volume': [100, 200, 300],
        })

        result = _normalize_ohlcv_frame(df, target_tz='America/New_York')

        assert result['open'].notna().all()
        assert result['open'].iloc[0] == 10.0
        assert len(result) == 3

    def test_capitalized_only_columns_work(self):
        """When only Capitalized columns exist, they should be used."""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=3, freq='1min', tz='UTC'),
            'Open': [20.0, 21.0, 22.0],
            'High': [20.5, 21.5, 22.5],
            'Low': [19.5, 20.5, 21.5],
            'Close': [20.2, 21.2, 22.2],
            'Volume': [1000, 2000, 3000],
        })

        result = _normalize_ohlcv_frame(df, target_tz='America/New_York')

        assert result['open'].notna().all()
        assert result['close'].iloc[-1] == 22.2
        assert len(result) == 3

    def test_missing_required_columns_raises(self):
        """Missing required columns should raise ValueError."""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=3, freq='1min', tz='UTC'),
            'open': [10.0, 11.0, 12.0],
            'high': [10.5, 11.5, 12.5],
            # Missing low, close, volume
        })

        with pytest.raises(ValueError, match="missing required columns"):
            _normalize_ohlcv_frame(df, target_tz='America/New_York')

    def test_timezone_conversion(self):
        """Test that timezone is correctly converted."""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01 14:30', periods=3, freq='1min', tz='UTC'),
            'Open': [100.0, 101.0, 102.0],
            'High': [100.5, 101.5, 102.5],
            'Low': [99.5, 100.5, 101.5],
            'Close': [100.2, 101.2, 102.2],
            'Volume': [1000, 2000, 3000],
        })

        result = _normalize_ohlcv_frame(df, target_tz='America/New_York')

        assert result.index.tz.zone == 'America/New_York'
        assert result.index.name == 'timestamp'
        # 14:30 UTC = 09:30 NY (in winter)
        assert result.index[0].hour == 9
        assert result.index[0].minute == 30
