"""
Tests for date filtering utilities.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from trading_dashboard.utils.date_filtering import (
    calculate_effective_date,
    apply_d1_window,
    apply_intraday_exact_day,
    WINDOW_BARS,
)


@pytest.fixture
def sample_daily_df():
    """Create sample daily data for testing."""
    # 300 trading days from 2024-01-02
    dates = pd.bdate_range(start="2024-01-02", periods=300, freq="B", tz="America/New_York")
    df = pd.DataFrame({
        "open": np.random.uniform(100, 110, 300),
        "high": np.random.uniform(110, 120, 300),
        "low": np.random.uniform(90, 100, 300),
        "close": np.random.uniform(100, 110, 300),
        "volume": np.random.randint(1000000, 10000000, 300),
    }, index=dates)
    return df


@pytest.fixture
def sample_intraday_df():
    """Create sample M5 intraday data for testing."""
    # Nov 20, 2024 - one full trading day
    start = pd.Timestamp("2024-11-20 09:30", tz="America/New_York")
    # 78 bars for a full day (9:30-16:00 = 6.5h = 78 x 5min)
    dates = pd.date_range(start=start, periods=78, freq="5min")
    df = pd.DataFrame({
        "open": np.random.uniform(100, 110, 78),
        "high": np.random.uniform(110, 120, 78),
        "low": np.random.uniform(90, 100, 78),
        "close": np.random.uniform(100, 110, 78),
        "volume": np.random.randint(10000, 100000, 78),
    }, index=dates)
    return df


def test_d1_window_slice_default_12m(sample_daily_df):
    """Test D1 window defaults to 12M (252 trading days)."""
    effective_date = sample_daily_df.index.max()

    result = apply_d1_window(sample_daily_df, effective_date, window="12M")

    # Should have 252 bars (or less if data < 252 days)
    assert len(result) <= 252
    assert len(result) == min(252, len(sample_daily_df))

    # Should end at effective_date
    assert result.index.max() == effective_date


def test_effective_date_clamping(sample_daily_df):
    """Test that requested date beyond max clamps to max."""
    max_date = sample_daily_df.index.max()
    future_date = (max_date + timedelta(days=30)).date()

    effective_date, reason = calculate_effective_date(future_date, sample_daily_df)

    # Should clamp to max
    assert effective_date == max_date
    assert reason == "clamped_max"

    # Test clamping to min
    min_date = sample_daily_df.index.min()
    past_date = (min_date - timedelta(days=30)).date()

    effective_date, reason = calculate_effective_date(past_date, sample_daily_df)

    assert effective_date == min_date
    assert reason == "clamped_min"


def test_effective_date_weekend_rolls_back(sample_daily_df):
    """Test that weekend/holiday rolls back to last trading day."""
    # Find a Friday in the data
    last_date = sample_daily_df.index.max()

    # Add 2 days to get to weekend (assuming Friday -> Sunday)
    # Actually let's be more explicit: request a Saturday
    # Find the last Friday
    for i in range(len(sample_daily_df) - 1, -1, -1):
        dt = sample_daily_df.index[i]
        if dt.dayofweek == 4:  # Friday
            friday = dt
            break

    # Request Saturday (next day)
    saturday = (friday + timedelta(days=1)).date()

    effective_date, reason = calculate_effective_date(saturday, sample_daily_df)

    # Should roll back to Friday
    assert effective_date == friday
    assert reason == "rolled_back"


def test_backtesting_date_filter_intraday_exact_day(sample_intraday_df):
    """Test intraday exact-day filtering."""
    # Request Nov 20, 2024
    effective_date = pd.Timestamp("2024-11-20", tz="America/New_York")

    result = apply_intraday_exact_day(sample_intraday_df, effective_date)

    # Should have all 78 bars (full trading day)
    assert len(result) == 78

    # All bars should be on Nov 20
    assert all(result.index.date == date(2024, 11, 20))

    # First bar should be 9:30 AM
    assert result.index[0].time() == pd.Timestamp("09:30").time()


def test_backtesting_date_filter_intraday_missing_day_empty_state():
    """Test intraday filtering returns empty when day missing."""
    # Create data for Nov 20 only
    dates = pd.date_range(
        start="2024-11-20 09:30",
        end="2024-11-20 16:00",
        freq="5min",
        tz="America/New_York"
    )
    df = pd.DataFrame({
        "open": [100] * len(dates),
        "close": [100] * len(dates),
        "high": [101] * len(dates),
        "low": [99] * len(dates),
        "volume": [1000] * len(dates),
    }, index=dates)

    # Request Nov 21 (not in data)
    effective_date = pd.Timestamp("2024-11-21", tz="America/New_York")

    result = apply_intraday_exact_day(df, effective_date)

    # Should be empty
    assert len(result) == 0
    assert result.empty


def test_d1_window_all_shows_full_history(sample_daily_df):
    """Test window='All' shows all data up to effective_date."""
    effective_date = sample_daily_df.index.max()

    result = apply_d1_window(sample_daily_df, effective_date, window="All")

    # Should have all data
    assert len(result) == len(sample_daily_df)
    assert result.index.min() == sample_daily_df.index.min()
    assert result.index.max() == effective_date


def test_window_bars_mapping():
    """Test that window bar counts are correct."""
    assert WINDOW_BARS["1M"] == 21
    assert WINDOW_BARS["3M"] == 63
    assert WINDOW_BARS["6M"] == 126
    assert WINDOW_BARS["12M"] == 252
    assert WINDOW_BARS["All"] is None


def test_calculate_effective_date_none_uses_latest(sample_daily_df):
    """Test that None requested_date uses latest available."""
    effective_date, reason = calculate_effective_date(None, sample_daily_df)

    assert effective_date == sample_daily_df.index.max()
    assert reason == "default_latest"


def test_intraday_timezone_conversion():
    """Test intraday filter handles timezone conversion."""
    # Create data in UTC
    dates = pd.date_range(
        start="2024-11-20 14:30",  # 9:30 AM NY in UTC
        periods=10,
        freq="5min",
        tz="UTC"
    )
    df = pd.DataFrame({
        "open": [100] * 10,
        "close": [100] * 10,
        "high": [101] * 10,
        "low": [99] * 10,
        "volume": [1000] * 10,
    }, index=dates)

    # Request Nov 20 in NY time
    effective_date = pd.Timestamp("2024-11-20", tz="America/New_York")

    result = apply_intraday_exact_day(df, effective_date, market_tz="America/New_York")

    # Should convert and filter
    assert len(result) == 10
    # Result should be in NY time
    assert str(result.index.tz) == "America/New_York"
