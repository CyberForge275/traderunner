#!/usr/bin/env python3
"""Inspect Rudometkin universe parquet file for debugging."""

import sys
from pathlib import Path
import pandas as pd

def inspect_universe(parquet_path: str):
    """Analyze universe parquet file."""
    path = Path(parquet_path)
    
    if not path.exists():
        print(f"❌ File not found: {path}")
        return 1
    
    print(f"📊 Loading universe: {path}")
    print(f"   Size: {path.stat().st_size / 1024 / 1024:.2f} MB\n")
    
    # Load the parquet
    df = pd.read_parquet(path)
    
    print("=" * 80)
    print("FILE STRUCTURE")
    print("=" * 80)
    print(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"Index type: {type(df.index).__name__}")
    if isinstance(df.index, pd.MultiIndex):
        print(f"Index levels: {df.index.names}")
    print(f"\nColumns: {list(df.columns)}")
    print(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
    
    # Detect symbol and date columns
    if isinstance(df.index, pd.MultiIndex):
        # Check if we need to reset or if columns already exist
        if "Date" in df.columns:
            # Date is both in index and columns, use the column
            symbol_col = df.index.names[0] if df.index.names[0] else "symbol"
            date_col = "Date"
            # Reset only the symbol level
            df = df.reset_index(level=0)
        else:
            df = df.reset_index()
            symbol_col = df.columns[0]
            date_col = df.columns[1]
        print(f"\n✓ MultiIndex detected, processed to columns")
    else:
        symbol_col = next((c for c in ["symbol", "Symbol", "ticker"] if c in df.columns), None)
        date_col = next((c for c in ["Date", "date", "timestamp"] if c in df.columns), None)
    
    if not symbol_col or not date_col:
        print(f"\n❌ Could not identify symbol/date columns")
        print(f"   Available columns: {list(df.columns)}")
        return 1
    
    print(f"\n✓ Symbol column: '{symbol_col}'")
    print(f"✓ Date column: '{date_col}'")
    
    # Get actual column names  
    if symbol_col not in df.columns:
        # symbol_col might be the index name, find the actual column
        actual_symbol_col = df.columns[0] if len(df.columns) > 0 else None
        if actual_symbol_col and actual_symbol_col != date_col:
            symbol_col = actual_symbol_col
    
    # Standardize for easier analysis
    df_work = df.rename(columns={symbol_col: "symbol", date_col: "date"})
    df_work["date"] = pd.to_datetime(df_work["date"])
    
    print("\n" + "=" * 80)
    print("DATE RANGE")
    print("=" * 80)
    min_date = df_work["date"].min()
    max_date = df_work["date"].max()
    print(f"Earliest: {min_date.date()}")
    print(f"Latest:   {max_date.date()}")
    print(f"Span:     {(max_date - min_date).days} days")
    
    # Unique symbols
    unique_symbols = df_work["symbol"].nunique()
    print(f"\n✓ Unique symbols: {unique_symbols:,}")
    
    # Last 5 days analysis
    print("\n" + "=" * 80)
    print("LAST 5 DAYS - STOCKS PER DAY")
    print("=" * 80)
    
    last_5_dates = df_work["date"].drop_duplicates().sort_values(ascending=False).head(5)
    
    for date in last_5_dates:
        day_data = df_work[df_work["date"] ==date]
        symbol_count = day_data["symbol"].nunique()
        row_count = len(day_data)
        print(f"{date.date()}: {symbol_count:4,} symbols ({row_count:5,} rows)")
    
    # Sample of latest day
    latest_day = df_work[df_work["date"] == max_date]
    print(f"\n" + "=" * 80)
    print(f"LATEST DAY SAMPLE ({max_date.date()})")
    print("=" * 80)
    sample_symbols = sorted(latest_day["symbol"].unique())[:20]
    print(f"First 20 symbols: {', '.join(sample_symbols)}")
    
    # Check for required columns
    print("\n" + "=" * 80)
    print("COLUMN AVAILABILITY")
    print("=" * 80)
    required = ["Open", "High", "Low", "Close", "Volume"]
    for col in required:
        has_it = col in df.columns or col.lower() in df.columns
        status = "✓" if has_it else "✗"
        print(f"{status} {col}")
    
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_universe.py <path_to_rudometkin.parquet>")
        print("\nExample:")
        print("  python inspect_universe.py data/universe/rudometkin.parquet")
        sys.exit(1)
    
    sys.exit(inspect_universe(sys.argv[1]))
