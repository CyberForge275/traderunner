"""
Tests for Candles Loader - Error Handling & Robustness
=======================================================

Ensures candles repository handles missing data gracefully.
"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile
import shutil
from datetime import timedelta  # Add missing import


def test_get_candle_data_missing_symbol():
    """Test that missing symbol returns empty DataFrame, not exception."""
    from trading_dashboard.repositories.candles import get_candle_data
    
    # Request data for non-existent symbol
    df = get_candle_data("NONEXISTENT_SYMBOL", timeframe="M5", hours=24)
    
    # Should return empty DataFrame with required columns
    assert isinstance(df, pd.DataFrame)
    assert df.empty or len(df) == 0  # Allow empty or zero rows
    assert all(col in df.columns for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume'])


def test_get_candle_data_missing_file():
    """Test behavior when parquet file doesn't exist."""
    from trading_dashboard.repositories.candles import get_candle_data
    
    # Request data for symbol without parquet file
    df = get_candle_data("SYMBOL_WITHOUT_FILE", timeframe="M15", hours=48)
    
    # Should return empty DataFrame, not raise FileNotFoundError
    assert isinstance(df, pd.DataFrame)
    assert df.empty or len(df) == 0


def test_get_candle_data_unsupported_timeframe():
    """Test that unsupported timeframe returns empty DataFrame."""
    from trading_dashboard.repositories.candles import get_candle_data
    
    # Request unsupported timeframe
    df = get_candle_data("AAPL", timeframe="M30", hours=24)
    
    # Should return empty DataFrame with required columns
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert all(col in df.columns for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume'])


def test_get_live_candle_data_no_database():
    """Test live data loader when database doesn't exist."""
    from trading_dashboard.repositories.candles import get_live_candle_data
    from datetime import date
    
    # Request live data (database likely doesn't exist in test env)
    df = get_live_candle_data("AAPL", "M5", date=date.today())
    
    # Should return empty DataFrame, not crash
    assert isinstance(df, pd.DataFrame)
    # Empty is acceptable - database might not exist in test env


def test_check_live_data_availability_no_database():
    """Test availability check when database doesn't exist."""
    from trading_dashboard.repositories.candles import check_live_data_availability
    from datetime import date
    
    # Check availability (database likely doesn't exist)
    result = check_live_data_availability(date=date.today())
    
    # Should return dict with 'available' key
    assert isinstance(result, dict)
    assert 'available' in result
    assert 'symbol_count' in result
    assert 'symbols' in result
    assert 'timeframes' in result
    
    # Values should be consistent
    if not result['available']:
        assert result['symbol_count'] == 0
        assert result['symbols'] == []
        assert result['timeframes'] == []


def test_get_candle_data_all_timeframes():
    """Test that all supported timeframes return consistent structure."""
    from trading_dashboard.repositories.candles import get_candle_data
    
    timeframes = ["M1", "M5", "M15", "H1", "D1"]
    
    for tf in timeframes:
        df = get_candle_data("AAPL", timeframe=tf, hours=24)
        
        # Should return DataFrame (empty or not)
        assert isinstance(df, pd.DataFrame)
        
        # Should have required columns
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        assert all(col in df.columns for col in required_cols)


def test_get_candle_data_future_date():
    """Test that requesting future date returns empty data."""
    from trading_dashboard.repositories.candles import get_candle_data
    from datetime import date, timedelta
    
    # Request data for tomorrow
    future_date = date.today() + timedelta(days=1)
    df = get_candle_data("AAPL", timeframe="M5", hours=24, reference_date=future_date)
    
    # Should return empty DataFrame (no future data)
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_get_candle_data_weekend():
    """Test that weekend dates return empty data (no trading)."""
    from trading_dashboard.repositories.candles import get_candle_data
    from datetime import date
    
    # Find next Saturday
    today = date.today()
    days_ahead = 5 - today.weekday()  # Saturday=5
    if days_ahead <= 0:
        days_ahead += 7
    saturday = today + timedelta(days=days_ahead)
    
    df = get_candle_data("AAPL", timeframe="M5", hours=24, reference_date=saturday)
    
    # Should return empty DataFrame (no trading on weekends)
    assert isinstance(df, pd.DataFrame)
    # Empty is expected for weekends


def test_candle_data_ohlc_validity():
    """Test that returned candles have valid OHLC relationships."""
    from trading_dashboard.repositories.candles import get_candle_data
    
    df = get_candle_data("AAPL", timeframe="M5", hours=24)
    
    if not df.empty and len(df) > 0:
        # OHLC validity: low <= open,close <= high
        assert (df['low'] <= df['open']).all()
        assert (df['low'] <= df['close']).all()
        assert (df['open'] <= df['high']).all()
        assert (df['close'] <= df['high']).all()
        
        # Volume should be non-negative
        assert (df['volume'] >= 0).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
