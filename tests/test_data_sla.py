"""
Tests for Data SLA Gate

Verifies gap-based completeness, base TF awareness, and FATAL/WARNING distinction.
"""

import pytest
import pandas as pd
import numpy as np
from typing import List

from backtest.services.data_sla import (
    check_data_sla,
    SLAResult,
    SLASeverity,
    SLAViolation
)


class TestSLANoNanOHLC:
    """Test no_nan_ohlc SLA (FATAL)."""
    
    def test_no_nan_ohlc_passes_with_clean_data(self):
        """Clean OHLC data passes."""
        df = _create_clean_data(bars=100, timeframe='M15')
        
        result = check_data_sla(df, 'inside_bar', 'M15', lookback_bars=50)
        
        # Should pass (no NaN)
        assert result.passed
        assert len([v for v in result.violations if v.sla_name == 'no_nan_ohlc']) == 0
    
    def test_no_nan_ohlc_fatal_with_nan_values(self):
        """NaN in OHLC is FATAL."""
        df = _create_clean_data(bars=100, timeframe='M15')
        # Inject NaN
        df.loc[df.index[50], 'close'] = np.nan
        
        result = check_data_sla(df, 'inside_bar', 'M15', lookback_bars=50)
        
        # Should fail
        assert not result.passed
        violations = [v for v in result.violations if v.sla_name == 'no_nan_ohlc']
        assert len(violations) == 1
        assert violations[0].severity == SLASeverity.FATAL
    
    def test_no_nan_ohlc_fatal_with_missing_columns(self):
        """Missing OHLC columns is FATAL."""
        df = pd.DataFrame({
            'volume': [1000] * 100
        }, index=pd.date_range('2025-01-01', periods=100, freq='15min', tz='America/New_York'))
        
        result = check_data_sla(df, 'inside_bar', 'M15', lookback_bars=50)
        
        # Should fail
        assert not result.passed
        violations = [v for v in result.violations if v.sla_name == 'no_nan_ohlc']
        assert len(violations) == 1
        assert violations[0].message == "OHLC columns not found"


class TestSLAGapBasedCompleteness:
    """Test gap-based completeness (FATAL for InsideBar)."""
    
    def test_gap_based_completeness_passes_without_gaps(self):
        """No gaps in lookback window → passes."""
        df = make_continuous_data(bars=100, timeframe='M15')
        
        result = check_data_sla(df, 'inside_bar', 'M15', lookback_bars=50)
        
        # Should pass (no gaps)
        assert result.passed
        fatal = result.fatal_violations()
        assert len([v for v in fatal if 'completeness' in v.sla_name and v.sla_name != 'm15_completeness_ratio']) == 0
    
    def test_gap_based_completeness_fatal_with_gaps(self):
        """
        REAL time gaps in lookback window → FATAL.
        
        Creates continuous 100 bars, then drops specific timestamps
        in the lookback window (last 50 bars).
        """
        # Create continuous data
        df = make_continuous_data(bars=100, timeframe='M15')
        
        # Drop 3 specific bars within lookback window (creates 45min gap)
        # Bars at indices 75, 76, 77 (within last 50)
        timestamps_to_drop = [
            df.index[75].isoformat(),  # e.g., "2025-01-01 10:00"
            df.index[76].isoformat(),  # "2025-01-01 10:15"
            df.index[77].isoformat(),  # "2025-01-01 10:30"
        ]
        
        df_with_gaps = drop_bars(df, timestamps_to_drop)
        
        result = check_data_sla(df_with_gaps, 'inside_bar', 'M15', lookback_bars=50)
        
        # Should fail (gaps detected)
        assert not result.passed, "Gap-based check should FAIL when real time gaps exist"
        
        violations = [v for v in result.violations if v.sla_name == 'm15_completeness']
        assert len(violations) == 1, f"Expected 1 m15_completeness violation, got {len(violations)}"
        assert violations[0].severity == SLASeverity.FATAL
        assert "gaps" in violations[0].message.lower()
        assert violations[0].measured_value == 3.0, f"Expected 3 missing bars, got {violations[0].measured_value}"
    
    def test_gap_based_completeness_requires_consecutive_bars(self):
        """
        InsideBar justification: Requires consecutive bars.
        
        - Mother bar at index[-2]
        - Inside bar at index[-1]
        - Breakout at current
        
        Any gap invalidates pattern.
        """
        # Create 100 bars, drop ONE bar in middle of lookback window
        df = make_continuous_data(bars=100, timeframe='M15')
        
        # Drop single bar at index 80 (within last 50 bars)
        timestamp_to_drop = df.index[80].isoformat()
        df_with_gap = drop_bars(df, [timestamp_to_drop])
        
        result = check_data_sla(df_with_gap, 'inside_bar', 'M15', lookback_bars=50)
        
        # Should fail (even 1 gap breaks consecutive requirement)
        assert not result.passed, "Even single gap should fail for InsideBar"
        assert len(result.fatal_violations()) > 0
    
    def test_shorter_continuous_data_passes_gap_check(self):
        """
        INVARIANT TEST: Shorter but continuous data should PASS gap check.
        
        This verifies distinction between:
        - "fewer bars but continuous" → PASS gap check (might fail min-bars)
        - "gaps in time series" → FAIL gap check
        """
        # Create only 40 continuous bars (less than lookback_bars=50)
        df = make_continuous_data(bars=40, timeframe='M15')
        
        result = check_data_sla(df, 'inside_bar', 'M15', lookback_bars=50)
        
        # Should FAIL due to insufficient bars, NOT due to gaps
        assert not result.passed
        
        # Verify: NO gap violation, only insufficient data
        gap_violations = [v for v in result.violations 
                         if v.sla_name == 'm15_completeness' and 'gaps' in v.message.lower()]
        assert len(gap_violations) == 0, "Continuous data should NOT have gap violations"
        
        # But should have insufficient data violation
        insufficient_violations = [v for v in result.violations 
                                  if 'insufficient' in v.message.lower()]
        assert len(insufficient_violations) > 0, "Should fail with insufficient data, not gaps"


class TestSLABaseTFAwareness:
    """Test base TF awareness (m5_completeness only if M5 is base)."""
    
    def test_m15_run_does_not_check_m5_completeness(self):
        """M15 is base TF → no m5_completeness check."""
        df = _create_clean_data(bars=100, timeframe='M15')
        
        result = check_data_sla(df, 'inside_bar', 'M15', lookback_bars=50)
        
        # Should NOT have m5_completeness violation
        # (M15 is base, only m15_completeness checked)
        m5_violations = [v for v in result.violations if 'm5' in v.sla_name]
        assert len(m5_violations) == 0
    
    def test_m5_run_checks_m5_completeness(self):
        """M5 is base TF → check m5_completeness."""
        df = _create_data_with_gaps(total_bars=100, gap_bars=3, timeframe='M5')
        
        result = check_data_sla(df, 'inside_bar', 'M5', lookback_bars=50)
        
        # Should have m5_completeness violation (base TF is M5)
        m5_violations = [v for v in result.violations if v.sla_name == 'm5_completeness']
        assert len(m5_violations) == 1
        assert m5_violations[0].severity == SLASeverity.FATAL
    
    def test_base_timeframe_reflected_in_result(self):
        """base_timeframe is reflected in result."""
        df = _create_clean_data(bars=100, timeframe='M15')
        
        result = check_data_sla(df, 'inside_bar', 'M15', lookback_bars=50)
        
        assert result.base_timeframe == 'M15'


class TestSLARatioBasedCompleteness:
    """Test ratio-based completeness (WARNING only, secondary check)."""
    
    def test_ratio_based_completeness_is_warning_not_fatal(self):
        """Ratio-based completeness is WARNING (gap-based is FATAL)."""
        # Create data with 80% completeness (similar to actual failure)
        df = _create_data_with_low_ratio(completeness=0.80, timeframe='M15')
        
        result = check_data_sla(df, 'inside_bar', 'M15', lookback_bars=50)
        
        # Might fail overall (due to gap-based), but ratio check is WARNING
        ratio_violations = [v for v in result.violations if 'ratio' in v.sla_name]
        if ratio_violations:
            assert ratio_violations[0].severity == SLASeverity.WARNING


class TestSLAInsufficientData:
    """Test insufficient data scenarios."""
    
    def test_insufficient_bars_for_lookback_fatal(self):
        """Less bars than lookback → FATAL."""
        df = _create_clean_data(bars=30, timeframe='M15')
        
        result = check_data_sla(df, 'inside_bar', 'M15', lookback_bars=50)
        
        # Should fail (30 < 50)
        assert not result.passed
        violations = [v for v in result.fatal_violations() if 'completeness' in v.sla_name]
        assert len(violations) >= 1
        assert any("insufficient" in v.message.lower() for v in violations)


# ===== HELPER FUNCTIONS =====

def make_continuous_data(bars: int, timeframe: str, start: str = '2025-01-01 09:30') -> pd.DataFrame:
    """
    Create continuous OHLC data without gaps (RTH only: 9:30-16:00).
    
    Args:
        bars: Number of bars to create
        timeframe: M1/M5/M15
        start: Start timestamp (should be during RTH)
    
    Returns:
        DataFrame with continuous RTH data (no gaps)
    """
    freq_map = {'M1': '1min', 'M5': '5min', 'M15': '15min'}
    
    # Generate enough dates to get desired bars (accounting for RTH filter)
    # M15: ~26 bars per day, so need ~4 days for 100 bars
    # Generate extra to be safe
    periods_needed = bars * 3
    
    dates = pd.date_range(
        start,
        periods=periods_needed,
        freq=freq_map[timeframe],
        tz='America/New_York'
    )
    
    # Filter to RTH only (9:30-16:00)
    rth_dates = dates[
        (dates.time >= pd.Timestamp("09:30").time()) &
        (dates.time <= pd.Timestamp("16:00").time())
    ]
    
    # Take exactly 'bars' number
    rth_dates = rth_dates[:bars]
    
    return pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.0,
        'volume': 1000
    }, index=rth_dates)


def drop_bars(df: pd.DataFrame, timestamps_to_drop: List[str]) -> pd.DataFrame:
    """
    Drop specific bars to create REAL time gaps.
    
    Args:
        df: Original DataFrame
        timestamps_to_drop: List of timestamp strings to drop
    
    Returns:
        DataFrame with specified timestamps removed (creates gaps)
    """
    # Convert timestamp strings to actual timestamps with TZ
    timestamps = [pd.Timestamp(ts, tz=df.index.tz or 'America/New_York') for ts in timestamps_to_drop]
    
    # Drop these timestamps
    df_with_gaps = df.drop(timestamps, errors='ignore')
    
    return df_with_gaps


def _create_clean_data(bars: int, timeframe: str) -> pd.DataFrame:
    """Create clean OHLC data without gaps (legacy helper)."""
    return make_continuous_data(bars, timeframe)


def _create_data_with_gaps(total_bars: int, gap_bars: int, timeframe: str) -> pd.DataFrame:
    """
    Create data with REAL time gaps (not just fewer bars).
    
    Creates continuous data then drops specific bars in the lookback window.
    """
    # Start with continuous data
    df = make_continuous_data(total_bars, timeframe)
    
    # Drop bars within lookback window (last 50 bars)
    # For total_bars=100, lookback is indices 50-99
    # Drop bars around index 75-80 (within lookback)
    
    gap_start_idx = total_bars - 30  # 30 bars from end (within lookback of 50)
    timestamps_to_drop = [df.index[i].isoformat() for i in range(gap_start_idx, gap_start_idx + gap_bars)]
    
    return drop_bars(df, timestamps_to_drop)


def _create_data_with_low_ratio(completeness: float, timeframe: str) -> pd.DataFrame:
    """Create data with specific completeness ratio (legacy helper)."""
    freq_map = {'M1': '1min', 'M5': '5min', 'M15': '15min'}
    
    # Create full range
    dates_full = pd.date_range(
        '2025-01-01 09:30',
        '2025-01-10 16:00',
        freq=freq_map[timeframe],
        tz='America/New_York'
    )
    
    # Sample to achieve target completeness
    actual_bars = int(len(dates_full) * completeness)
    dates_sampled = dates_full[:actual_bars]
    
    return pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.0,
        'volume': 1000
    }, index=dates_sampled)
