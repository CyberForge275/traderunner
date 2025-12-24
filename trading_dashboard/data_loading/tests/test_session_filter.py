import pytest
import pandas as pd
from datetime import datetime
import pytz

from trading_dashboard.data_loading.filters.session_filter import SessionFilter


class TestSessionFilter:
    """Unit tests for SessionFilter."""

    @pytest.fixture
    def sample_data(self):
        """Create sample timestamps covering different sessions."""
        et_tz = pytz.timezone('America/New_York')

        timestamps = [
            # RTH
            et_tz.localize(datetime(2025, 12, 11, 9, 30)),   # Open
            et_tz.localize(datetime(2025, 12, 11, 12, 0)),   # Midday
            et_tz.localize(datetime(2025, 12, 11, 15, 55)),  # Near close

            # Pre-market
            et_tz.localize(datetime(2025, 12, 11, 8, 0)),
            et_tz.localize(datetime(2025, 12, 11, 9, 0)),

            # After-hours
            et_tz.localize(datetime(2025, 12, 11, 16, 30)),
            et_tz.localize(datetime(2025, 12, 11, 19, 0)),

            # Weekend
            et_tz.localize(datetime(2025, 12, 13, 12, 0)),  # Saturday
            et_tz.localize(datetime(2025, 12, 14, 12, 0)),  # Sunday
        ]

        return pd.DataFrame({
            'timestamp': timestamps,
            'close': [100.0] * len(timestamps)
        })

    def test_filter_to_rth_includes_trading_hours(self, sample_data):
        """RTH filter should include 9:30-16:00 ET."""
        result = SessionFilter.filter_to_rth(sample_data)

        # Should have exactly 3 RTH candles
        assert len(result) == 3

        # Verify times
        result_times = pd.to_datetime(result['timestamp']).dt.tz_convert(
            SessionFilter.ET_TZ
        ).dt.time

        for t in result_times:
            assert SessionFilter.RTH_START <= t < SessionFilter.RTH_END

    def test_filter_to_rth_excludes_premarket(self, sample_data):
        """Filter should exclude pre-market (before 9:30)."""
        result = SessionFilter.filter_to_rth(sample_data)

        result_times = pd.to_datetime(result['timestamp']).dt.tz_convert(
            SessionFilter.ET_TZ
        ).dt.time

        for t in result_times:
            assert t >= SessionFilter.RTH_START

    def test_filter_to_rth_excludes_afterhours(self, sample_data):
        """Filter should exclude after-hours (after 16:00)."""
        result = SessionFilter.filter_to_rth(sample_data)

        result_times = pd.to_datetime(result['timestamp']).dt.tz_convert(
            SessionFilter.ET_TZ
        ).dt.time

        for t in result_times:
            assert t < SessionFilter.RTH_END

    def test_filter_to_rth_excludes_weekend(self, sample_data):
        """Filter should exclude Saturday and Sunday."""
        result = SessionFilter.filter_to_rth(sample_data)

        result_days = pd.to_datetime(result['timestamp']).dt.tz_convert(
            SessionFilter.ET_TZ
        ).dt.dayofweek

        for day in result_days:
            assert day < 5  # Monday=0, Friday=4

    def test_is_rth_time_single_timestamp(self):
        """Test single timestamp RTH check."""
        et_tz = pytz.timezone('America/New_York')

        # RTH
        rth_time = et_tz.localize(datetime(2025, 12, 11, 10, 0))
        assert SessionFilter.is_rth_time(rth_time) is True

        # Pre-market
        pre_time = et_tz.localize(datetime(2025, 12, 11, 8, 0))
        assert SessionFilter.is_rth_time(pre_time) is False

        # After-hours
        after_time = et_tz.localize(datetime(2025, 12, 11, 17, 0))
        assert SessionFilter.is_rth_time(after_time) is False

        # Weekend
        weekend_time = et_tz.localize(datetime(2025, 12, 13, 12, 0))
        assert SessionFilter.is_rth_time(weekend_time) is False

    def test_empty_dataframe(self):
        """Filter should handle empty DataFrame."""
        empty_df = pd.DataFrame(columns=['timestamp', 'close'])
        result = SessionFilter.filter_to_rth(empty_df)

        assert len(result) == 0
        assert 'timestamp' in result.columns

    def test_missing_timestamp_column(self):
        """Should raise ValueError if timestamp missing."""
        bad_df = pd.DataFrame({'close': [100.0]})

        with pytest.raises(ValueError, match="timestamp"):
            SessionFilter.filter_to_rth(bad_df)
