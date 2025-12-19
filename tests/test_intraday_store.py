from __future__ import annotations

from pathlib import Path

import pandas as pd

from axiom_bt.intraday import IntradayStore, Timeframe


def test_intraday_store_normalizes_frame(tmp_path: Path, monkeypatch) -> None:
    """IntradayStore.load should normalize timestamp index and OHLCV columns."""

    # Create a dummy M5 parquet with timestamp column and OHLCV in title case
    path = tmp_path / "AAPL.parquet"
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=3, freq="5min", tz="UTC"),
            "Open": [1.0, 2.0, 3.0],
            "High": [1.5, 2.5, 3.5],
            "Low": [0.5, 1.5, 2.5],
            "Close": [1.2, 2.2, 3.2],
            "Volume": [100, 200, 300],
        }
    )
    df.to_parquet(path)

    # Patch DATA_M5 location to our tmp_path
    import axiom_bt.fs as fs

    monkeypatch.setattr(fs, "DATA_M5", tmp_path)

    store = IntradayStore(default_tz="America/New_York")
    frame = store.load("aapl", timeframe=Timeframe.M5)

    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert frame.index.name == "timestamp"
    assert frame.index.tz is not None
    # Ensure we converted to the configured timezone
    assert str(frame.index.tz) == "America/New_York"


# ========================================================================
# Gap Detection Tests for check_local_m1_coverage()
# ========================================================================

def test_check_local_m1_coverage_no_file(tmp_path: Path, monkeypatch) -> None:
    """When parquet file doesn't exist, entire requested range should be a gap."""
    import axiom_bt.fs as fs
    monkeypatch.setattr(fs, "DATA_M1", tmp_path)
    
    from axiom_bt.intraday import check_local_m1_coverage
    
    result = check_local_m1_coverage(
        symbol="NONEXISTENT",
        start="2024-12-01",
        end="2024-12-19",
        tz="America/New_York"
    )
    
    assert result["has_gap"] is True
    assert result["available_days"] == 0
    assert result["requested_days"] == 19
    assert len(result["gaps"]) == 1
    
    gap = result["gaps"][0]
    assert gap["gap_start"] == "2024-12-01"
    assert gap["gap_end"] == "2024-12-19"
    assert gap["gap_days"] == 19


def test_check_local_m1_coverage_gap_before_existing(tmp_path: Path, monkeypatch) -> None:
    """When existing data starts after requested start, should detect gap before."""
    import axiom_bt.fs as fs
    monkeypatch.setattr(fs, "DATA_M1", tmp_path)
    
    from axiom_bt.intraday import check_local_m1_coverage
    
    # Create parquet with data from Dec 1-19
    path = tmp_path / "AAPL.parquet"
    timestamps = pd.date_range("2024-12-01", "2024-12-19", freq="1h", tz="UTC")
    n = len(timestamps)
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "Open": [100.0] * n,
            "High": [101.0] * n,
            "Low": [99.0] * n,
            "Close": [100.5] * n,
            "Volume": [1000] * n,
        }
    )
    df.to_parquet(path)
    
    # Request Oct 1 - Dec 19 (need historical data)
    result = check_local_m1_coverage(
        symbol="AAPL",
        start="2024-10-01",
        end="2024-12-19",
        tz="America/New_York"
    )
    
    assert result["has_gap"] is True
    assert result["earliest_data"] == "2024-12-01"
    assert result["latest_data"] == "2024-12-19"
    assert len(result["gaps"]) == 1
    
    gap = result["gaps"][0]
    assert gap["gap_start"] == "2024-10-01"
    assert gap["gap_end"] == "2024-11-30"  # Day before existing data
    assert gap["gap_days"] == 61  # Oct (31) + Nov (30)
    assert gap["reason"] == "before_existing_data"


def test_check_local_m1_coverage_gap_after_existing(tmp_path: Path, monkeypatch) -> None:
    """When existing data ends before requested end, should detect gap after."""
    import axiom_bt.fs as fs
    monkeypatch.setattr(fs, "DATA_M1", tmp_path)
    
    from axiom_bt.intraday import check_local_m1_coverage
    
    # Create parquet with data from Oct 1 - Nov 30
    path = tmp_path / "AAPL.parquet"
    timestamps = pd.date_range("2024-10-01", "2024-11-30", freq="1h", tz="UTC")
    n = len(timestamps)
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "Open": [100.0] * n,
            "High": [101.0] * n,
            "Low": [99.0] * n,
            "Close": [100.5] * n,
            "Volume": [1000] * n,
        }
    )
    df.to_parquet(path)
    
    # Request Oct 1 - Dec 31 (need future data)
    result = check_local_m1_coverage(
        symbol="AAPL",
        start="2024-10-01",
        end="2024-12-31",
        tz="America/New_York"
    )
    
    assert result["has_gap"] is True
    assert result["earliest_data"] == "2024-10-01"
    assert result["latest_data"] == "2024-11-30"
    assert len(result["gaps"]) == 1
    
    gap = result["gaps"][0]
    assert gap["gap_start"] == "2024-12-01"  # Day after existing data
    assert gap["gap_end"] == "2024-12-31"
    assert gap["gap_days"] == 31  # December
    assert gap["reason"] == "after_existing_data"


def test_check_local_m1_coverage_both_gaps(tmp_path: Path, monkeypatch) -> None:
    """When existing data has gaps before AND after, should detect both."""
    import axiom_bt.fs as fs
    monkeypatch.setattr(fs, "DATA_M1", tmp_path)
    
    from axiom_bt.intraday import check_local_m1_coverage
    
    # Create parquet with data ONLY for November
    path = tmp_path / "AAPL.parquet"
    timestamps = pd.date_range("2024-11-01", "2024-11-30", freq="1h", tz="UTC")
    n = len(timestamps)
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "Open": [100.0] * n,
            "High": [101.0] * n,
            "Low": [99.0] * n,
            "Close": [100.5] * n,
            "Volume": [1000] * n,
        }
    )
    df.to_parquet(path)
    
    # Request Oct 1 - Dec 31 (need data before AND after)
    result = check_local_m1_coverage(
        symbol="AAPL",
        start="2024-10-01",
        end="2024-12-31",
        tz="America/New_York"
    )
    
    assert result["has_gap"] is True
    assert result["earliest_data"] == "2024-11-01"
    assert result["latest_data"] == "2024-11-30"
    assert len(result["gaps"]) == 2
    
    # Gap 1: Before (October)
    gap1 = result["gaps"][0]
    assert gap1["gap_start"] == "2024-10-01"
    assert gap1["gap_end"] == "2024-10-31"
    assert gap1["gap_days"] == 31
    assert gap1["reason"] == "before_existing_data"
    
    # Gap 2: After (December)
    gap2 = result["gaps"][1]
    assert gap2["gap_start"] == "2024-12-01"
    assert gap2["gap_end"] == "2024-12-31"
    assert gap2["gap_days"] == 31
    assert gap2["reason"] == "after_existing_data"


def test_check_local_m1_coverage_no_gap(tmp_path: Path, monkeypatch) -> None:
    """When existing data fully covers requested range, should have no gaps."""
    import axiom_bt.fs as fs
    monkeypatch.setattr(fs, "DATA_M1", tmp_path)
    
    from axiom_bt.intraday import check_local_m1_coverage
    
    # Create parquet with data from Oct 1 - Dec 31 (wide range)
    path = tmp_path / "AAPL.parquet"
    timestamps = pd.date_range("2024-10-01", "2024-12-31", freq="1h", tz="UTC")
    n = len(timestamps)
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "Open": [100.0] * n,
            "High": [101.0] * n,
            "Low": [99.0] * n,
            "Close": [100.5] * n,
            "Volume": [1000] * n,
        }
    )
    df.to_parquet(path)
    
    # Request Nov 1 - Nov 30 (subset of existing data)
    result = check_local_m1_coverage(
        symbol="AAPL",
        start="2024-11-01",
        end="2024-11-30",
        tz="America/New_York"
    )
    
    assert result["has_gap"] is False
    assert result["earliest_data"] == "2024-10-01"
    assert result["latest_data"] == "2024-12-31"
    assert result["available_days"] == 92  # Oct (31) + Nov (30) + Dec (31)
    assert result["requested_days"] == 30  # November
    assert len(result["gaps"]) == 0  # No gaps!


def test_check_local_m1_coverage_exact_match(tmp_path: Path, monkeypatch) -> None:
    """When existing data exactly matches requested range, should have no gaps."""
    import axiom_bt.fs as fs
    monkeypatch.setattr(fs, "DATA_M1", tmp_path)
    
    from axiom_bt.intraday import check_local_m1_coverage
    
    # Create parquet with data for November only
    path = tmp_path / "AAPL.parquet"
    timestamps = pd.date_range("2024-11-01", "2024-11-30", freq="1h", tz="UTC")
    n = len(timestamps)
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "Open": [100.0] * n,
            "High": [101.0] * n,
            "Low": [99.0] * n,
            "Close": [100.5] * n,
            "Volume": [1000] * n,
        }
    )
    df.to_parquet(path)
    
    # Request exactly November
    result = check_local_m1_coverage(
        symbol="AAPL",
        start="2024-11-01",
        end="2024-11-30",
        tz="America/New_York"
    )
    
    assert result["has_gap"] is False
    assert result["earliest_data"] == "2024-11-01"
    assert result["latest_data"] == "2024-11-30"
    assert len(result["gaps"]) == 0
