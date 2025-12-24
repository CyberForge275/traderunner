#!/usr/bin/env python3
"""
Convert AutomatedStockPicker parquet to universe format.

Source: /data/workspace/AutomatedStockPicker/tradingcrew_2023/backtest/bt_cks/daily_lists/stocks_data.parquet
Target: /opt/trading/traderunner/artifacts/data_d1/universe_YYYY.parquet
"""
import pandas as pd
from pathlib import Path
import sys

# Source file
SOURCE = Path('/data/workspace/AutomatedStockPicker/tradingcrew_2023/backtest/bt_cks/daily_lists/stocks_data.parquet')
TARGET_DIR = Path('/opt/trading/traderunner/artifacts/data_d1')

def convert_stocks_data():
    """Convert stocks_data.parquet to universe format."""
    print(f"📂 Loading source: {SOURCE}")

    if not SOURCE.exists():
        print(f"❌ Source file not found: {SOURCE}")
        sys.exit(1)

    # Load data
    df = pd.read_parquet(SOURCE)
    print(f"  ✅ Loaded {len(df)} rows")
    print(f"  Columns: {df.columns.tolist()}")
    print(f"  Index: {df.index.names}")

    # This file has multi-index (symbol, Date) where Date is also a column
    # Extract symbol from index level 0
    if isinstance(df.index, pd.MultiIndex) or df.index.name is None:
        # Get symbol from first index level
        df['symbol'] = df.index.get_level_values(0) if isinstance(df.index, pd.MultiIndex) else df.index

        # Drop Date column if exists (it's duplicate of index)
        if 'Date' in df.columns:
            df = df.drop(columns=['Date'])

        # Reset index completely
        df = df.reset_index(drop=False)

        # Now we should have Date from index
        print(f"  Index converted, columns now: {df.columns.tolist()}")


    # Normalize column names (case insensitive)
    rename_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if col_lower == 'date':
            rename_map[col] = 'timestamp'
        elif col_lower in ['open', 'high', 'low', 'close', 'volume']:
            rename_map[col] = col_lower
        elif col_lower == 'adj_close':
            rename_map[col] = 'adj_close'

    df = df.rename(columns=rename_map)

    # Ensure timestamp is datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Drop unnecessary columns
    keep_cols = ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']
    if 'adj_close' in df.columns:
        keep_cols.append('adj_close')

    df = df[keep_cols]

    # Get year range
    years = df['timestamp'].dt.year.unique()
    print(f"\n📅 Years in data: {sorted(years)}")

    # Create target directory
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Split by year and save
    for year in sorted(years):
        year_df = df[df['timestamp'].dt.year == year].copy()

        if year_df.empty:
            continue

        target_file = TARGET_DIR / f'universe_{year}.parquet'
        year_df.to_parquet(target_file, compression='snappy', index=False)

        file_size_mb = target_file.stat().st_size / 1024 / 1024
        symbols_count = year_df['symbol'].nunique()
        rows_count = len(year_df)

        print(f"\n  ✅ {year}: {target_file.name}")
        print(f"     Size: {file_size_mb:.2f} MB")
        print(f"     Symbols: {symbols_count:,}")
        print(f"     Rows: {rows_count:,}")
        print(f"     Date range: {year_df['timestamp'].min().date()} to {year_df['timestamp'].max().date()}")

    print(f"\n✅ Conversion complete!")
    print(f"📂 Files saved to: {TARGET_DIR}")

    # Verify
    print(f"\n🔍 Verification:")
    files = sorted(TARGET_DIR.glob('universe_*.parquet'))
    for f in files:
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  {f.name}: {size_mb:.2f} MB")

if __name__ == '__main__':
    try:
        convert_stocks_data()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
