"""Integration tests for RTH parity validation."""
import pytest
import pandas as pd
from datetime import datetime, time as time_class
import pytz

from trading_dashboard.data_loading.filters.session_filter import SessionFilter
from trading_dashboard.data_loading.loaders.eodhd_backfill import EODHDBackfill


class TestRTHParity:
    """
    Test RTH parity between backtest and live data.
    
    Goal: Ensure RTH filtering produces identical results across systems.
    """
    
    @pytest.fixture
    def mixed_session_data(self):
        """Create data with pre-market, RTH, and after-hours."""
        et_tz = pytz.timezone('America/New_York')
        base_date = datetime(2025, 12, 11)
        
        timestamps = []
        
        # Pre-market: 8:00-9:25
        for hour in [8, 9]:
            for minute in range(0, 60, 5):
                if hour == 9 and minute >= 30:
                    continue
                timestamps.append(et_tz.localize(
                    base_date.replace(hour=hour, minute=minute)
                ))
        
        # RTH: 9:30-16:00
        for hour in range(9, 16):
            for minute in range(0, 60, 5):
                if hour == 9 and minute < 30:
                    continue
                timestamps.append(et_tz.localize(
                    base_date.replace(hour=hour, minute=minute)
                ))
        
        # After-hours: 16:00-20:00
        for hour in range(16, 20):
            for minute in range(0, 60, 5):
                timestamps.append(et_tz.localize(
                    base_date.replace(hour=hour, minute=minute)
                ))
        
        return pd.DataFrame({
            'timestamp': timestamps,
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000
        })
    
    @pytest.mark.integration
    def test_rth_filter_produces_expected_count(self, mixed_session_data):
        """
        Verify RTH filter produces exactly 78 candles for a full trading day.
        
        Math: 9:30-16:00 = 390 minutes / 5 min intervals = 78 candles
        """
        session_filter = SessionFilter()
        
        rth_only = session_filter.filter_to_rth(mixed_session_data)
        
        # Verify count
        assert len(rth_only) == 78, f"Expected 78 RTH candles, got {len(rth_only)}"
        
        # Verify all timestamps are within RTH
        et_tz = pytz.timezone('America/New_York')
        for ts in rth_only['timestamp']:
            ts_et = pd.to_datetime(ts).tz_convert(et_tz)
            t = ts_et.time()
            assert time_class(9, 30) <= t < time_class(16, 0), \
                f"Timestamp {ts_et} outside RTH"
    
    @pytest.mark.integration
    def test_rth_filter_excludes_all_non_rth(self, mixed_session_data):
        """
        Verify RTH filter removes ALL non-RTH candles.
        """
        session_filter = SessionFilter()
        
        total_count = len(mixed_session_data)
        rth_count = len(session_filter.filter_to_rth(mixed_session_data))
        
        removed_count = total_count - rth_count
        
        # Should have removed pre-market + after-hours
        # Pre: ~18 candles (8:00-9:25)
        # After: ~48 candles (16:00-20:00)
        # Total removed: ~66 candles
        
        assert removed_count > 60, \
            f"Should have removed ~66 candles (pre+after), removed {removed_count}"
        
        assert rth_count == 78, \
            f"Should have exactly 78 RTH candles, got {rth_count}"
    
    @pytest.mark.integration
    def test_rth_boundaries_exact(self, mixed_session_data):
        """
        Test exact RTH boundaries: 9:30 included, 16:00 excluded.
        """
        session_filter = SessionFilter()
        rth_only = session_filter.filter_to_rth(mixed_session_data)
        
        et_tz = pytz.timezone('America/New_York')
        times = pd.to_datetime(rth_only['timestamp']).dt.tz_convert(et_tz).dt.time
        
        # First candle should be 9:30
        assert times.iloc[0] == time_class(9, 30), \
            f"First RTH candle should be 9:30, got {times.iloc[0]}"
        
        # Last candle should be 15:55 (not 16:00)
        assert times.iloc[-1] == time_class(15, 55), \
            f"Last RTH candle should be 15:55, got {times.iloc[-1]}"
    
    @pytest.mark.integration
    def test_weekend_exclusion(self):
        """
        Verify weekends are completely excluded.
        """
        et_tz = pytz.timezone('America/New_York')
        
        # Create Saturday data during RTH hours
        saturday = datetime(2025, 12, 13, 12, 0)  # Saturday noon
        saturday_candles = pd.DataFrame({
            'timestamp': [et_tz.localize(saturday)],
            'close': [100.0]
        })
        
        session_filter = SessionFilter()
        result = session_filter.filter_to_rth(saturday_candles)
        
        assert len(result) == 0, "Saturday candles should be filtered out"
        
        # Create Sunday data
        sunday = datetime(2025, 12, 14, 12, 0)  # Sunday noon
        sunday_candles = pd.DataFrame({
            'timestamp': [et_tz.localize(sunday)],
            'close': [100.0]
        })
        
        result = session_filter.filter_to_rth(sunday_candles)
        
        assert len(result) == 0, "Sunday candles should be filtered out"
    
    @pytest.mark.integration
    def test_backfill_produces_rth_only(self):
        """
        Verify EODHDBackfill automatically filters to RTH.
        
        This ensures parity: backfill data = RTH only, no manual filtering needed.
        """
        # This would require real EODHD API or extensive mocking
        # For now, we rely on unit tests + manual validation
        # Mark as integration test that needs EODHD_API_KEY
        
        pytest.skip("Requires EODHD API access - validated in manual testing")
