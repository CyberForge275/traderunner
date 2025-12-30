"""Unit tests for DailyDataLoader."""
import pytest
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import shutil
from pathlib import Path

from trading_dashboard.data_loading.loaders.daily_data_loader import DailyDataLoader


@pytest.fixture
def temp_data_dir():
    """Create temporary directory with test data."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create test data for 2024
    data_2024 = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', '2024-12-31', freq='D'),
        'symbol': ['AAPL'] * 366,
        'open': 150.0,
        'high': 152.0,
        'low': 148.0,
        'close': 151.0,
        'volume': 1000000
    })

    # Add TSLA data
    tsla_2024 = data_2024.copy()
    tsla_2024['symbol'] = 'TSLA'
    tsla_2024['close'] = 250.0

    combined_2024 = pd.concat([data_2024, tsla_2024])
    combined_2024.to_parquet(temp_dir / 'universe_2024.parquet')

    # Create test data for 2025
    data_2025 = pd.DataFrame({
        'timestamp': pd.date_range('2025-01-01', '2025-03-31', freq='D'),
        'symbol': ['AAPL'] * 90,
        'open': 160.0,
        'high': 162.0,
        'low': 158.0,
        'close': 161.0,
        'volume': 1200000
    })

    data_2025.to_parquet(temp_dir / 'universe_2025.parquet')

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


class TestDailyDataLoader:
    """Tests for DailyDataLoader."""

    def test_load_single_symbol(self, temp_data_dir):
        """Should load data for single symbol."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        df = loader.load_data(
            'AAPL',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )

        assert len(df) == 31
        assert (df['symbol'] == 'AAPL').all()
        assert df['close'].iloc[0] == 151.0

    def test_load_multiple_symbols(self, temp_data_dir):
        """Should load data for multiple symbols."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        df = loader.load_data(
            ['AAPL', 'TSLA'],
            start_date='2024-01-01',
            end_date='2024-01-31'
        )

        assert len(df) == 62  # 31 days * 2 symbols
        assert set(df['symbol'].unique()) == {'AAPL', 'TSLA'}

    def test_load_days_back(self, temp_data_dir):
        """Should load N days back from today."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        # Load last 10 days (will get 2025 data)
        df = loader.load_data('AAPL', days_back=10)

        assert len(df) <= 10
        assert (df['symbol'] == 'AAPL').all()

    def test_load_across_years(self, temp_data_dir):
        """Should load Data spanning multiple years."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        df = loader.load_data(
            'AAPL',
            start_date='2024-12-01',
            end_date='2025-01-31'
        )

        # Should have December 2024 + January 2025
        assert len(df) == 31 + 31  # Dec + Jan
        assert df['timestamp'].min() >= pd.Timestamp('2024-12-01')
        assert df['timestamp'].max() <= pd.Timestamp('2025-01-31')

    def test_get_available_symbols(self, temp_data_dir):
        """Should return list of available symbols."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        symbols_2024 = loader.get_available_symbols(2024)
        assert set(symbols_2024) == {'AAPL', 'TSLA'}

        symbols_2025 = loader.get_available_symbols(2025)
        assert symbols_2025 == ['AAPL']

    def test_get_available_years(self, temp_data_dir):
        """Should return list of available years."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        years = loader.get_available_years()
        assert years == [2024, 2025]

    def test_get_latest_update(self, temp_data_dir):
        """Should return latest data timestamp."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        latest = loader.get_latest_update(2024)
        assert latest == pd.Timestamp('2024-12-31')

        latest_2025 = loader.get_latest_update(2025)
        assert latest_2025 == pd.Timestamp('2025-03-31')

    def test_cache_functionality(self, temp_data_dir):
        """Should cache loaded years."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        # First load
        df1 = loader.load_data('AAPL', start_date='2024-01-01', end_date='2024-01-31')

        # Should be cached
        assert 2024 in loader._cache

        # Second load should use cache
        df2 = loader.load_data('AAPL', start_date='2024-01-01', end_date='2024-01-31')

        pd.testing.assert_frame_equal(df1, df2)

        # Clear cache
        loader.clear_cache()
        assert len(loader._cache) == 0

    def test_empty_result_for_missing_symbol(self, temp_data_dir):
        """Should return empty DataFrame for non-existent symbol."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        df = loader.load_data('INVALID', start_date='2024-01-01', end_date='2024-01-31')

        assert df.empty

    def test_sorted_by_timestamp(self, temp_data_dir):
        """Should return data sorted by timestamp."""
        loader = DailyDataLoader(data_dir=str(temp_data_dir))

        df = loader.load_data(
            ['AAPL', 'TSLA'],
            start_date='2024-01-01',
            end_date='2024-01-10'
        )

        assert df['timestamp'].is_monotonic_increasing
