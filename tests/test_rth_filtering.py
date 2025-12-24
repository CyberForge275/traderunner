"""
Test RTH (Regular Trading Hours) filtering implementation.

Verifies that:
1. filter_rth_session() correctly filters data to 09:30-16:00 ET
2. fetch_intraday_1m_to_parquet() creates both raw and RTH files
3. RTH-filtered data excludes Pre-Market and After-Hours
"""

import pytest
import pandas as pd
from datetime import datetime, time
from pathlib import Path
import tempfile
import shutil

from axiom_bt.data.session_filter import filter_rth_session, get_rth_stats
from axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet


def test_filter_rth_session_basic():
    """Test basic RTH filtering with mixed session data."""
    # Create test data with Pre-Market, RTH, and After-Hours
    timestamps = pd.date_range(
        start="2024-12-10 04:00:00",  # Pre-Market start
        end="2024-12-10 20:00:00",    # After-Hours end
        freq="1h",
        tz="America/New_York"
    )

    df = pd.DataFrame({
        "Open": range(len(timestamps)),
        "High": range(len(timestamps)),
        "Low": range(len(timestamps)),
        "Close": range(len(timestamps)),
        "Volume": [1000] * len(timestamps),
    }, index=timestamps)

    # Filter to RTH
    df_rth = filter_rth_session(df, tz="America/New_York")

    # Verify only RTH hours remain (09:30-16:00)
    for ts in df_rth.index:
        ts_ny = ts.tz_convert("America/New_York")
        assert ts_ny.time() >= time(9, 30), f"Found timestamp before RTH: {ts_ny}"
        assert ts_ny.time() < time(16, 0), f"Found timestamp after RTH: {ts_ny}"

    # Verify we have the expected hours (10:00, 11:00, ..., 15:00)
    # Note: 09:30 not in hourly data, 16:00 is exclusive
    expected_hours = {10, 11, 12, 13, 14, 15}
    actual_hours = {ts.tz_convert("America/New_York").hour for ts in df_rth.index}
    assert actual_hours == expected_hours


def test_filter_rth_session_utc_input():
    """Test RTH filtering with UTC timestamps (EODHD format)."""
    # Create UTC timestamps that correspond to NY times
    # 14:30 UTC = 09:30 EST (during winter)
    # 20:00 UTC = 15:00 EST
    timestamps_utc = pd.date_range(
        start="2024-12-10 14:30:00",  # 09:30 EST
        end="2024-12-10 21:00:00",    # 16:00 EST (should be excluded)
        freq="30min",
        tz="UTC"
    )

    df = pd.DataFrame({
        "Open": range(len(timestamps_utc)),
        "High": range(len(timestamps_utc)),
        "Low": range(len(timestamps_utc)),
        "Close": range(len(timestamps_utc)),
        "Volume": [1000] * len(timestamps_utc),
    }, index=timestamps_utc)

    # Filter to RTH
    df_rth = filter_rth_session(df, tz="America/New_York")

    # Verify we got the expected range (09:30-15:30 EST, excluding 16:00)
    assert len(df_rth) == 13  # 14:30, 15:00, ..., 20:30 UTC (excluding 21:00)

    # Verify all timestamps are within RTH when converted to NY
    for ts in df_rth.index:
        ts_ny = ts.tz_convert("America/New_York")
        assert ts_ny.time() >= time(9, 30)
        assert ts_ny.time() < time(16, 0)


def test_get_rth_stats():
    """Test RTH statistics calculation."""
    # Create 24-hour data
    timestamps = pd.date_range(
        start="2024-12-10 00:00:00",
        end="2024-12-10 23:59:00",
        freq="1min",
        tz="America/New_York"
    )

    df = pd.DataFrame({
        "Close": [100.0] * len(timestamps),
        "Volume": [1000] * len(timestamps),
    }, index=timestamps)

    stats = get_rth_stats(df, tz="America/New_York")

    # Verify stats structure
    assert "total_rows" in stats
    assert "rth_rows" in stats
    assert "pre_market_rows" in stats
    assert "after_hours_rows" in stats
    assert "rth_percentage" in stats

    # RTH is 09:30-16:00 = 6.5 hours = 390 minutes
    assert stats["rth_rows"] == 390

    # Pre-Market is 04:00-09:30 = 5.5 hours = 330 minutes
    assert stats["pre_market_rows"] == 330

    # After-Hours is 16:00-20:00 = 4 hours = 240 minutes
    assert stats["after_hours_rows"] == 240

    # Total = 1440 minutes in a day
    assert stats["total_rows"] == 1440

    # RTH percentage should be ~27.1%
    assert 26 < stats["rth_percentage"] < 28


def test_fetch_creates_raw_and_rth_files():
    """Test that fetch creates both raw and RTH-filtered files."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_rth_"))

    try:
        # Fetch sample data
        path = fetch_intraday_1m_to_parquet(
            symbol="TEST",
            exchange="US",
            start_date="2024-12-01",
            end_date="2024-12-05",
            out_dir=temp_dir,
            tz="America/New_York",
            use_sample=True,  # Use sample data
            save_raw=True,
            filter_rth=True,
        )

        # Verify both files exist
        raw_path = temp_dir / "TEST_raw.parquet"
        rth_path = temp_dir / "TEST.parquet"

        assert raw_path.exists(), "Raw file should be created"
        assert rth_path.exists(), "RTH-filtered file should be created"

        # Load both files
        df_raw = pd.read_parquet(raw_path)
        df_rth = pd.read_parquet(rth_path)

        # RTH should be smaller than raw
        assert len(df_rth) < len(df_raw), "RTH-filtered data should be smaller than raw"

        # Get stats on raw data
        stats = get_rth_stats(df_raw, tz="America/New_York")

        # RTH file should have exactly the RTH rows from raw
        assert len(df_rth) == stats["rth_rows"], \
            f"RTH file should have {stats['rth_rows']} rows, got {len(df_rth)}"

        # Verify RTH percentage is reasonable (20-50%)
        assert 20 < stats["rth_percentage"] < 50, \
            f"RTH percentage {stats['rth_percentage']:.1f}% seems wrong"

    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def test_rth_filter_preserves_columns():
    """Test that RTH filtering preserves all OHLCV columns."""
    timestamps = pd.date_range(
        start="2024-12-10 09:00:00",
        end="2024-12-10 17:00:00",
        freq="1h",
        tz="America/New_York"
    )

    df = pd.DataFrame({
        "Open": [100.0] * len(timestamps),
        "High": [101.0] * len(timestamps),
        "Low": [99.0] * len(timestamps),
        "Close": [100.5] * len(timestamps),
        "Volume": [10000] * len(timestamps),
    }, index=timestamps)

    df_rth = filter_rth_session(df)

    # Verify all columns preserved
    assert list(df_rth.columns) == ["Open", "High", "Low", "Close", "Volume"]

    # Verify data types preserved
    assert df_rth["Volume"].dtype == df["Volume"].dtype


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
