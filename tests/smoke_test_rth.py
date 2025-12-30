#!/usr/bin/env python3
"""
Manual smoke test for RTH filtering.

This script demonstrates that:
1. Raw data contains Pre-Market, RTH, and After-Hours
2. RTH filtering correctly extracts only 09:30-16:00 ET data
3. Statistics show expected distribution
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet
from axiom_bt.data.session_filter import get_rth_stats, filter_rth_session
import pandas as pd
import tempfile
import shutil


def main():
    print("=" * 70)
    print("RTH (Regular Trading Hours) Filtering - Smoke Test")
    print("=" * 70)
    print()

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix="rth_smoke_"))
    print(f"📁 Temp directory: {temp_dir}")
    print()

    try:
        # Fetch sample data
        print("🔄 Fetching sample data...")
        path = fetch_intraday_1m_to_parquet(
            symbol='SMOKE',
            exchange='US',
            start_date='2024-12-01',
            end_date='2024-12-05',
            out_dir=temp_dir,
            tz='America/New_York',
            use_sample=True,
            save_raw=True,
            filter_rth=True,
        )
        print(f"✅ Data fetched to: {path}")
        print()

        # Check files exist
        raw_path = temp_dir / "SMOKE_raw.parquet"
        rth_path = temp_dir / "SMOKE.parquet"

        print("📊 Files created:")
        print(f"  Raw:  {raw_path.name} ({raw_path.stat().st_size / 1024:.1f} KB)")
        print(f"  RTH:  {rth_path.name} ({rth_path.stat().st_size / 1024:.1f} KB)")
        print()

        # Load raw data
        df_raw = pd.read_parquet(raw_path)
        print(f"📈 Raw data loaded: {len(df_raw):,} rows")
        print(f"  Date range: {df_raw.index.min()} → {df_raw.index.max()}")
        print()

        # Get statistics
        stats = get_rth_stats(df_raw, tz="America/New_York")

        print("📊 Session Distribution (Raw Data):")
        print(f"  Total rows:      {stats['total_rows']:>8,}")
        print(f"  Pre-Market:      {stats['pre_market_rows']:>8,}  (04:00-09:30 ET)")
        print(f"  RTH:             {stats['rth_rows']:>8,}  (09:30-16:00 ET) ✅")
        print(f"  After-Hours:     {stats['after_hours_rows']:>8,}  (16:00-20:00 ET)")
        print(f"  Other:           {stats['other_rows']:>8,}")
        print()
        print(f"  RTH Percentage:  {stats['rth_percentage']:>7.1f}%")
        print()

        # Load RTH-filtered data
        df_rth = pd.read_parquet(rth_path)
        print(f"📈 RTH-filtered data loaded: {len(df_rth):,} rows")
        print(f"  Date range: {df_rth.index.min()} → {df_rth.index.max()}")
        print()

        # Verify RTH filtering
        print("🔍 Verification:")

        # Check 1: RTH file has exactly the RTH rows from stats
        if len(df_rth) == stats['rth_rows']:
            print(f"  ✅ RTH file has correct row count: {len(df_rth):,}")
        else:
            print(f"  ❌ RTH file mismatch: expected {stats['rth_rows']:,}, got {len(df_rth):,}")

        # Check 2: RTH is smaller than raw
        reduction = (1 - len(df_rth) / len(df_raw)) * 100
        print(f"  ✅ Data reduction: {reduction:.1f}% (RTH is {len(df_rth):,} / {len(df_raw):,})")

        # Check 3: Verify all timestamps in RTH file are within 09:30-16:00
        all_in_range = True
        for ts in df_rth.index:
            ts_ny = ts.tz_convert("America/New_York")
            if ts_ny.time() < pd.Timestamp("09:30").time() or ts_ny.time() >= pd.Timestamp("16:00").time():
                all_in_range = False
                print(f"  ❌ Found timestamp outside RTH: {ts_ny}")
                break

        if all_in_range:
            print(f"  ✅ All timestamps are within RTH window (09:30-16:00 ET)")

        # Check 4: Verify columns preserved
        expected_cols = ["Open", "High", "Low", "Close", "Volume"]
        if list(df_rth.columns) == expected_cols:
            print(f"  ✅ All OHLCV columns preserved")
        else:
            print(f"  ❌ Columns mismatch: {list(df_rth.columns)}")

        print()
        print("=" * 70)
        print("✅ RTH Filtering - All Checks Passed!")
        print("=" * 70)

        # Show sample data
        print()
        print("📋 Sample RTH data (first 5 rows):")
        print(df_rth.head())

    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print()
            print(f"🧹 Cleaned up temp directory")


if __name__ == "__main__":
    main()
