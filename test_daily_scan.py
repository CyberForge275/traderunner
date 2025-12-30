#!/usr/bin/env python3
"""Test Rudometkin daily scan for a specific date."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from strategies.rudometkin_moc.strategy import RudometkinMOCStrategy


def run_daily_scan_for_date(universe_path: str, target_date: str):
    """Run daily scan for a specific date and show results."""

    print(f"🔍 Running Rudometkin Daily Scan for {target_date}")
    print("=" * 80)

    # Load universe
    df = pd.read_parquet(universe_path)
    print(f"✓ Loaded universe: {len(df):,} rows")

    # Handle MultiIndex
    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index(level=0)

    # Standardize column names
    if "Date" in df.columns:
        df = df.rename(columns={df.columns[0]: "symbol", "Date": "timestamp"})

    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Filter with 300-day lookback buffer (same as pipeline fix)
    target_dt = pd.Timestamp(target_date)
    LOOKBACK_DAYS = 300
    lookback_start = target_dt - pd.Timedelta(days=LOOKBACK_DAYS)

    # Get historical data with buffer
    historical_data = df[
        (df["timestamp"] >= lookback_start) &
        (df["timestamp"] <= target_dt)
    ].copy()

    if historical_data.empty:
        print(f"❌ No data found for {target_date} with {LOOKBACK_DAYS}-day lookback")
        return

    actual_min_date = historical_data["timestamp"].min()
    actual_lookback = (target_dt - actual_min_date).days

    print(f"✓ Using historical data: {actual_min_date.date()} to {target_dt.date()}")
    print(f"  Lookback: {actual_lookback} days")
    print(f"  Total rows: {len(historical_data):,}")

    # Rename columns to match strategy expectations
    historical_data = historical_data.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })

    # Get symbols that have data on the target date
    target_day_symbols = historical_data[
        historical_data["timestamp"].dt.date == target_dt.date()
    ]["symbol"].unique()

    print(f"\n📊 Scanning {len(target_day_symbols)} symbols with historical context...")
    print("=" * 80)

    # Default Rudometkin config
    config = {
        "min_price": 10.0,
        "min_average_volume": 1_000_000,
        "adx_threshold": 35.0,
        "adx_period": 5,
        "sma_period": 200,
        "atr40_ratio_bounds": {"min": 0.01, "max": 0.10},
        "atr2_ratio_bounds": {"min": 0.01, "max": 0.20},
        "crsi_threshold": 70.0,
        "crsi_price_rsi": 2,
        "crsi_streak_rsi": 2,
        "crsi_rank_period": 100,
    }

    # Initialize strategy
    strategy = RudometkinMOCStrategy()

    # Track results
    long_candidates = []
    short_candidates = []
    filtered_out = {}

    for symbol in target_day_symbols:
        symbol_data = historical_data[historical_data["symbol"] == symbol].copy()

        # Need to prepare data with timestamp
        symbol_data = symbol_data[["timestamp", "open", "high", "low", "close", "volume"]].copy()

        try:
            signals = strategy.generate_signals(symbol_data, symbol, config)

            if signals:
                for sig in signals:
                    score = sig.metadata.get("score", 0)
                    setup = sig.metadata.get("setup", "unknown")

                    if sig.signal_type.upper() == "LONG":
                        long_candidates.append({
                            "symbol": symbol,
                            "score": score,
                            "setup": setup,
                            "entry": sig.entry_price
                        })
                    elif sig.signal_type.upper() == "SHORT":
                        short_candidates.append({
                            "symbol": symbol,
                            "score": score,
                            "setup": setup,
                            "entry": sig.entry_price
                        })
        except Exception as e:
            reason = type(e).__name__
            filtered_out[symbol] = reason

    # Sort by score (descending)
    long_candidates.sort(key=lambda x: x["score"], reverse=True)
    short_candidates.sort(key=lambda x: x["score"], reverse=True)

    print(f"\n✅ LONG CANDIDATES ({len(long_candidates)} total)")
    print("=" * 80)
    if long_candidates:
        print(f"{'Rank':<5} {'Symbol':<8} {'Score':<10} {'Setup':<15} {'Entry':<10}")
        print("-" * 80)
        for i, cand in enumerate(long_candidates[:20], 1):  # Top 20
            print(f"{i:<5} {cand['symbol']:<8} {cand['score']:<10.4f} {cand['setup']:<15} ${cand['entry']:<9.2f}")

        if len(long_candidates) > 20:
            print(f"\n... and {len(long_candidates) - 20} more")
    else:
        print("No LONG candidates found")

    print(f"\n✅ SHORT CANDIDATES ({len(short_candidates)} total)")
    print("=" * 80)
    if short_candidates:
        print(f"{'Rank':<5} {'Symbol':<8} {'Score':<10} {'Setup':<15} {'Entry':<10}")
        print("-" * 80)
        for i, cand in enumerate(short_candidates[:20], 1):  # Top 20
            print(f"{i:<5} {cand['symbol']:<8} {cand['score']:<10.4f} {cand['setup']:<15} ${cand['entry']:<9.2f}")

        if len(short_candidates) > 20:
            print(f"\n... and {len(short_candidates) - 20} more")
    else:
        print("No SHORT candidates found")

    # Summary
    total_scanned = len(day_data["symbol"].unique())
    total_qualified = len(long_candidates) + len(short_candidates)

    print(f"\n📈 SUMMARY")
    print("=" * 80)
    print(f"Total scanned:     {total_scanned:4,}")
    print(f"LONG candidates:   {len(long_candidates):4,}")
    print(f"SHORT candidates:  {len(short_candidates):4,}")
    print(f"Filtered out:      {len(filtered_out):4,}")
    print(f"Pass rate:         {(total_qualified/total_scanned*100):.1f}%")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_daily_scan.py <universe_path> <date>")
        print("\nExample:")
        print("  python test_daily_scan.py data/universe/rudometkin.parquet 2025-11-21")
        sys.exit(1)

    run_daily_scan_for_date(sys.argv[1], sys.argv[2])
