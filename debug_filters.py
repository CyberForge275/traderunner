#!/usr/bin/env python3
"""Debug why Rudometkin filters are rejecting all stocks."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def debug_filters_for_date(universe_path: str, target_date: str, sample_size: int = 20):
    """Debug filter failures for specific stocks."""

    print(f"🔍 Debugging Rudometkin Filters for {target_date}")
    print("=" * 80)

    # Load universe
    df = pd.read_parquet(universe_path)

    # Handle MultiIndex
    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index(level=0)

    # Standardize
    if "Date" in df.columns:
        df = df.rename(columns={df.columns[0]: "symbol", "Date": "timestamp"})

    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Get data for target date AND historical context (need 200 days for SMA)
    target_dt = pd.Timestamp(target_date)
    lookback_start = target_dt - pd.Timedelta(days=300)  # Extra buffer

    historical_data = df[
        (df["timestamp"] >= lookback_start) &
        (df["timestamp"] <= target_dt)
    ].copy()

    print(f"✓ Loaded historical data: {lookback_start.date()} to {target_dt.date()}")
    print(f"  Total rows: {len(historical_data):,}")

    # Get symbols from target date
    target_day = df[df["timestamp"].dt.date == target_dt.date()]
    sample_symbols = target_day["symbol"].unique()[:sample_size]

    print(f"\n📊 Testing {len(sample_symbols)} sample symbols from {target_date}")
    print("=" * 80)

    # Rename for calculations
    historical_data = historical_data.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })

    # Check each sample symbol
    for symbol in sample_symbols:
        symbol_hist = historical_data[historical_data["symbol"] == symbol].sort_values("timestamp")

        if len(symbol_hist) < 200:
            print(f"\n{symbol}: ❌ REJECTED - Not enough history ({len(symbol_hist)} days < 200)")
            continue

        latest = symbol_hist.iloc[-1]

        print(f"\n{symbol}: Checking filters...")
        print(f"  Latest close: ${latest['close']:.2f}")
        print(f"  Latest volume: {latest['volume']:,.0f}")
        print(f"  Days of data: {len(symbol_hist)}")

        # Filter 1: Price
        if latest['close'] < 10.0:
            print(f"  ❌ Price filter: ${latest['close']:.2f} < $10.00")
            continue
        else:
            print(f"  ✓ Price filter passed")

        # Filter 2: Volume (50-day average)
        if len(symbol_hist) >= 50:
            avg_vol_50 = symbol_hist['volume'].tail(50).mean()
            if avg_vol_50 < 1_000_000:
                print(f"  ❌ Volume filter: {avg_vol_50:,.0f} < 1,000,000")
                continue
            else:
                print(f"  ✓ Volume filter passed: {avg_vol_50:,.0f}")

        # Check if we have enough data for indicators
        print(f"  ✓ Basic filters passed - Ready for indicator calculation")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python debug_filters.py <universe_path> <date> [sample_size]")
        print("\nExample:")
        print("  python debug_filters.py data/universe/rudometkin.parquet 2025-11-21 20")
        sys.exit(1)

    sample = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    debug_filters_for_date(sys.argv[1], sys.argv[2], sample)
