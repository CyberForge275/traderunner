"""
Unit tests for SessionFilter UTC → NY timezone bug.

CRITICAL BUG: SessionFilter.is_in_session() checks timestamps in their original timezone
(often UTC) against NY session windows, without converting to NY first.

This causes:
- 09:15 EST = 14:15 UTC → falls in 14:00-15:00 window → WRONGLY ACCEPTED
- Should be: convert 14:15 UTC → 09:15 EST → reject (before 10:00)
"""

import pytest
import pandas as pd
from strategies.inside_bar.config import SessionFilter


def test_session_filter_utc_to_ny_conversion_bug():
    """
    CRITICAL: Test that UTC timestamps are converted to NY before checking.
    
    Scenario:
    - Session windows: 10:00-11:00, 14:00-15:00 (America/New_York)
    - Timestamp: 2025-12-12 14:15:00 UTC
    - In UTC: 14:15 falls in 14:00-15:00 → would PASS (BUG!)
    - In NY: 14:15 UTC = 09:15 EST → should FAIL (before 10:00)
    
    Expected: REJECTED (timestamp is 09:15 EST, before 10:00)
    """
    session_filter = SessionFilter.from_strings(["10:00-11:00", "14:00-15:00"])
    
    # UTC timestamp that corresponds to 09:15 EST (before session start)
    ts_utc = pd.Timestamp("2025-12-12 14:15:00", tz="UTC")
    
    # Convert to NY to verify our assumption
    ts_ny = ts_utc.tz_convert("America/New_York")
    assert ts_ny.hour == 9  # 09:15 EST
    assert ts_ny.minute == 15
    
    # The filter MUST reject this (it's 09:15 EST, before 10:00)
    result = session_filter.is_in_session(ts_utc, tz="America/New_York")
    
    assert result == False, (
        f"BUG REPRODUCED! Timestamp {ts_utc} (= {ts_ny.strftime('%H:%M')} EST) "
        f"should be REJECTED (before 10:00 EST) but was ACCEPTED!"
    )


def test_session_filter_utc_to_ny_multiple_cases():
    """Test multiple UTC times that should be rejected in NY."""
    session_filter = SessionFilter.from_strings(["10:00-11:00", "14:00-15:00"])
    
    # All these UTC times = morning EST times (before 10:00)
    # During winter (EST = UTC-5):
    # 14:15 UTC = 09:15 EST
    # 14:20 UTC = 09:20 EST
    # 14:35 UTC = 09:35 EST
    
    test_cases = [
        ("2025-12-12 14:15:00", "09:15 EST", False),  # Before 10:00
        ("2025-12-12 14:20:00", "09:20 EST", False),  # Before 10:00
        ("2025-12-12 14:35:00", "09:35 EST", False),  # Before 10:00
        ("2025-12-12 15:25:00", "10:25 EST", True),   # In 10:00-11:00
        ("2025-12-12 15:30:00", "10:30 EST", True),   # In 10:00-11:00
        ("2025-12-12 19:25:00", "14:25 EST", True),   # In 14:00-15:00
    ]
    
    for utc_time_str, est_label, expected in test_cases:
        ts_utc = pd.Timestamp(utc_time_str, tz="UTC")
        result = session_filter.is_in_session(ts_utc, tz="America/New_York")
        
        assert result == expected, (
            f"FAILED for {utc_time_str} UTC ({est_label}): "
            f"expected {expected}, got {result}"
        )


def test_session_filter_naive_timestamp_treated_as_utc():
    """
    Test that naive timestamps are treated as UTC (EODHD convention).
    
    Scenario:
    - Naive timestamp: 2025-12-12 14:15:00 (no timezone)
    - Should be interpreted as UTC
    - Then converted to NY → 09:15 EST
    - Should be REJECTED
    """
    session_filter = SessionFilter.from_strings(["10:00-11:00", "14:00-15:00"])
    
    # Naive timestamp (EODHD intraday data format)
    ts_naive = pd.Timestamp("2025-12-12 14:15:00")  # No tz
    assert ts_naive.tz is None
    
    # Should be treated as UTC, then converted to NY
    # 14:15 UTC = 09:15 EST → should REJECT
    result = session_filter.is_in_session(ts_naive, tz="America/New_York")
    
    assert result == False, (
        f"Naive timestamp {ts_naive} should be treated as UTC (14:15), "
        f"= 09:15 EST, and REJECTED"
    )


def test_session_filter_already_in_ny_timezone():
    """Test that NY-native timestamps work correctly."""
    session_filter = SessionFilter.from_strings(["10:00-11:00", "14:00-15:00"])
    
    # Already in NY timezone
    ts_ny_morning = pd.Timestamp("2025-12-12 09:15:00", tz="America/New_York")
    ts_ny_in_session = pd.Timestamp("2025-12-12 10:25:00", tz="America/New_York")
    
    assert session_filter.is_in_session(ts_ny_morning, tz="America/New_York") == False
    assert session_filter.is_in_session(ts_ny_in_session, tz="America/New_York") == True


if __name__ == "__main__":
    # Run tests - these should FAIL with current implementation
    print("Testing SessionFilter UTC → NY conversion bug...")
    print()
    
    try:
        test_session_filter_utc_to_ny_conversion_bug()
        print("✅ test_session_filter_utc_to_ny_conversion_bug PASSED")
    except AssertionError as e:
        print(f"❌ test_session_filter_utc_to_ny_conversion_bug FAILED (expected):")
        print(f"   {e}")
    
    try:
        test_session_filter_utc_to_ny_multiple_cases()
        print("✅ test_session_filter_utc_to_ny_multiple_cases PASSED")
    except AssertionError as e:
        print(f"❌ test_session_filter_utc_to_ny_multiple_cases FAILED (expected):")
        print(f"   {e}")
    
    try:
        test_session_filter_naive_timestamp_treated_as_utc()
        print("✅ test_session_filter_naive_timestamp_treated_as_utc PASSED")
    except AssertionError as e:
        print(f"❌ test_session_filter_naive_timestamp_treated_as_utc FAILED (expected):")
        print(f"   {e}")
    
    try:
        test_session_filter_already_in_ny_timezone()
        print("✅ test_session_filter_already_in_ny_timezone PASSED")
    except AssertionError as e:
        print(f"❌ test_session_filter_already_in_ny_timezone FAILED:")
        print(f"   {e}")
