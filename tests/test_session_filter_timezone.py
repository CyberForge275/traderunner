"""
Regression test for session filter timezone consistency bug.

Bug: SessionFilter.is_in_session() was called without timezone parameter,
causing it to use default Europe/Berlin instead of configured market timezone.

This test proves the fix works by setting up a scenario where:
- Config uses America/New_York timezone
- Session window is 15:00-17:00 (intended as NY time)
- Signal timestamp is 09:35 EST (= 15:35 CET)

Without fix: is_in_session() would use Berlin TZ → 09:35 EST converts to 15:35 CET → IN session (WRONG!)
With fix: is_in_session() uses NY TZ → 09:35 EST stays 09:35 EST → OUT of session (CORRECT!)
"""
import pytest
import pandas as pd
from strategies.inside_bar.config import SessionFilter, InsideBarConfig
from strategies.inside_bar.core import InsideBarCore, RawSignal


def test_session_filter_respects_configured_timezone():
    """
    Regression test: Session filter must use configured timezone, not default.

    Scenario:
    - Market TZ: America/New_York
    - Session window: 15:00-17:00 (NY afternoon)
    - Signal timestamp: 2025-12-17 09:35:00-05:00 (NY morning)

    Expected: Signal is OUTSIDE session (09:35 < 15:00 in same TZ)
    Bug behavior: Signal would be IN session (if converted to Berlin, 09:35 EST = 15:35 CET)
    """
    # Setup config with NY timezone and afternoon session
    config = InsideBarConfig(
        session_timezone="America/New_York",
        session_windows=["15:00-17:00"],  # As string list, not SessionFilter object
        atr_period=14,
        min_mother_bar_size=0.5,
        risk_reward_ratio=2.0,
    )

    core = InsideBarCore(config)

    # Create mock OHLC data with morning pattern
    # Mother bar at 09:30, inside bar at 09:35
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-12-17 09:30:00', periods=10, freq='5min', tz='America/New_York'),
        'open': [121.0, 120.9, 120.8, 120.7, 121.1, 121.2, 121.3, 121.4, 121.5, 121.6],
        'high': [122.0, 121.0, 120.9, 120.8, 121.5, 121.7, 121.8, 121.9, 122.0, 122.1],  # Inside bar at idx 1
        'low':  [120.5, 120.8, 120.7, 120.6, 120.9, 121.0, 121.1, 121.2, 121.3, 121.4],   # Inside bar at idx 1
        'close': [121.5, 120.95, 120.75, 120.65, 121.3, 121.5, 121.6, 121.7, 121.8, 121.9],
    })

    # Process data - this applies session filter
    signals = core.process_data(df, symbol='TEST')

    # CRITICAL ASSERTION:
    # Session filter is 15:00-17:00 NY time
    # All timestamps in df are 09:30-10:15 NY time (morning)
    # Therefore: NO signals should pass the filter
    assert len(signals) == 0, (
        f"Expected 0 signals (all outside 15:00-17:00 NY session), "
        f"but got {len(signals)}. "
        f"This indicates session filter is using wrong timezone!"
    )


def test_session_filter_allows_signals_in_correct_timezone():
    """
    Positive test: Signals within session window should pass filter.

    Scenario:
    - Market TZ: America/New_York
    - Session window: 10:00-11:00 (NY morning)
    - Pattern forms at 10:05, breakout at 10:10

    Expected: Signal passes filter (in window)
    """
    config = InsideBarConfig(
        session_timezone="America/New_York",
        session_windows=["10:00-11:00"],  # As string list
        atr_period=14,
        min_mother_bar_size=0.0,  # Disable size filter for test
        risk_reward_ratio=2.0,
    )

    core = InsideBarCore(config)

    # Create pattern within session window
    # Mother bar at 10:00, inside bar at 10:05, breakout at 10:10
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-12-17 10:00:00', periods=5, freq='5min', tz='America/New_York'),
        'open':  [120.0, 120.5, 120.3, 121.0, 121.5],
        'high':  [121.0, 120.8, 120.5, 121.5, 122.0],  # Mother=121.0, Inside=120.8, Breakout=122.0
        'low':   [119.5, 120.2, 120.1, 120.8, 121.0],  # Mother=119.5, Inside=120.2
        'close': [120.5, 120.4, 120.3, 121.3, 121.8],
    })

    signals = core.process_data(df, symbol='TEST')

    # Should have at least 1 signal (breakout at 10:10 is in session 10:00-11:00)
    assert len(signals) >= 1, (
        f"Expected at least 1 signal (breakout in 10:00-11:00 session), "
        f"but got {len(signals)}"
    )

    # Verify signal timestamp is within session
    for sig in signals:
        ts = pd.to_datetime(sig.timestamp).tz_convert('America/New_York')
        hour_minute = ts.strftime('%H:%M')
        assert '10:00' <= hour_minute < '11:00', (
            f"Signal at {hour_minute} is outside session window 10:00-11:00"
        )


if __name__ == "__main__":
    # Run tests directly
    test_session_filter_respects_configured_timezone()
    print("✓ test_session_filter_respects_configured_timezone PASSED")

    test_session_filter_allows_signals_in_correct_timezone()
    print("✓ test_session_filter_allows_signals_in_correct_timezone PASSED")

    print("\nAll regression tests PASSED!")
