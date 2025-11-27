#!/usr/bin/env python3
"""Test Stage 2: Check if daily candidates trigger intraday signals."""

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from axiom_bt.intraday import IntradayStore, Timeframe
from strategies.rudometkin_moc.strategy import RudometkinMOCStrategy


def test_intraday_triggers(
    data_dir: Path,
    test_date: str,
    top_longs: list,
    top_shorts: list,
):
    """Test if top candidates trigger signals on intraday data."""
    
    print(f"🔍 Testing Intraday Signal Generation for {test_date}")
    print("=" * 80)
    
    strategy = RudometkinMOCStrategy()
    
    # Default config
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
        "entry_stretch1": 0.035,
        "entry_stretch2": 0.05,
    }
    
    target_date = pd.Timestamp(test_date)
    
    # Test LONG candidates
    print(f"\n{'='*80}")
    print(f"TESTING {len(top_longs)} LONG CANDIDATES")
    print("=" * 80)
    
    long_signals_found = 0
    for symbol in top_longs:
        result = _test_symbol(
            strategy, symbol, data_dir, target_date, config, expected_direction="LONG"
        )
        if result > 0:
            long_signals_found += result
    
    # Test SHORT candidates
    print(f"\n{'='*80}")
    print(f"TESTING {len(top_shorts)} SHORT CANDIDATES")
    print("=" * 80)
    
    short_signals_found = 0
    for symbol in top_shorts:
        result = _test_symbol(
            strategy, symbol, data_dir, target_date, config, expected_direction="SHORT"
        )
        if result > 0:
            short_signals_found += result
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print("=" * 80)
    print(f"LONG candidates tested:  {len(top_longs)}")
    print(f"LONG signals generated:  {long_signals_found}")
    print(f"SHORT candidates tested: {len(top_shorts)}")
    print(f"SHORT signals generated: {short_signals_found}")
    print(f"\nTotal signals: {long_signals_found + short_signals_found}")


def _test_symbol(
    strategy,
    symbol: str,
    data_dir: Path,
    target_date: pd.Timestamp,
    config: dict,
    expected_direction: str,
) -> int:
    """Test one symbol for intraday signals."""
    
    store = IntradayStore(default_tz="America/New_York")
    try:
        df = store.load(symbol, timeframe=Timeframe.M5)
    except FileNotFoundError:
        parquet_file = data_dir / f"{symbol}.parquet"
        print(f"\n{symbol}: ❌ No intraday data file: {parquet_file}")
        return 0
    except Exception as e:
        print(f"\n{symbol}: ❌ Failed to load data: {e}")
        return 0

    # Get enough historical data (300 days before target)
    # Make timestamps timezone-aware to match data
    if df["timestamp"].dt.tz is not None:
        tz = df["timestamp"].dt.tz
        lookback_start = target_date - pd.Timedelta(days=300)
        lookback_start = lookback_start.tz_localize(tz)
        target_end = (target_date + pd.Timedelta(days=1)).tz_localize(tz)
    else:
        lookback_start = target_date - pd.Timedelta(days=300)
        target_end = target_date + pd.Timedelta(days=1)
    
    df_filtered = df[
        (df.index >= lookback_start) &
        (df.index <= target_end)
    ].copy()
    
    if df_filtered.empty:
        print(f"\n{symbol}: ❌ No data for date range")
        return 0
    
    # Standardize columns
    df_filtered = df_filtered.reset_index().rename(columns={"timestamp": "timestamp"})
    
    # Check minimum data
    if len(df_filtered) < 200:
        print(f"\n{symbol}: ❌ Not enough data ({len(df_filtered)} bars < 200)")
        return 0
    
    # Generate signals
    try:
        signals = strategy.generate_signals(df_filtered, symbol, config)
    except Exception as e:
        print(f"\n{symbol}: ❌ Signal generation failed: {type(e).__name__}: {e}")
        return 0
    
    if not signals:
        print(f"\n{symbol}: ⚠️  No signals generated (conditions not met on intraday data)")
        return 0
    
    # Filter to target date only
    target_day_signals = [
        s for s in signals
        if pd.Timestamp(s.timestamp).date() == target_date.date()
    ]
    
    if not target_day_signals:
        print(f"\n{symbol}: ⚠️  {len(signals)} signals total, but none on target date {target_date.date()}")
        return 0
    
    # Show results
    print(f"\n{symbol}: ✅ {len(target_day_signals)} {expected_direction} signal(s) on {target_date.date()}")
    
    for i, sig in enumerate(target_day_signals[:3], 1):  # Show first 3
        sig_time = pd.Timestamp(sig.timestamp)
        print(f"  [{i}] {sig_time.strftime('%H:%M:%S')} - "
              f"{sig.signal_type} @ ${sig.entry_price:.2f} "
              f"(score: {sig.metadata.get('score', 0):.2f})")
    
    if len(target_day_signals) > 3:
        print(f"  ... and {len(target_day_signals) - 3} more")
    
    return len(target_day_signals)


if __name__ == "__main__":
    # Use major stocks that have data available for testing
    # These represent what would be filtered symbols from daily scan
    TEST_SYMBOLS = ["AAPL", "TSLA", "NVDA", "GOOGL", "MSFT"]
    
    print("NOTE: Testing with major stocks (AAPL, TSLA, NVDA, GOOGL, MSFT)")
    print("      These may not meet Rudometkin setup criteria, but demonstrate Stage 2 logic\n")
    
    # Check for data directories
    data_m5 = ROOT / "artifacts" / "data_m5"
    data_m15 = ROOT / "artifacts" / "data_m15"
    data_m1 = ROOT / "artifacts" / "data_m1"
    
    # Try M5 first, then M15, then M1
    if data_m5.exists() and any(data_m5.glob("*.parquet")):
        print(f"📁 Using M5 data from: {data_m5}")
        data_dir = data_m5
    elif data_m15.exists() and any(data_m15.glob("*.parquet")):
        print(f"📁 Using M15 data from: {data_m15}")
        data_dir = data_m15
    elif data_m1.exists() and any(data_m1.glob("*.parquet")):
        print(f"📁 Using M1 data from: {data_m1}")
        data_dir = data_m1
    else:
        print("❌ No intraday data found in artifacts/data_m5, data_m15, or data_m1")
        print("   Run a data fetch first or use sample data")
        sys.exit(1)
    
    test_intraday_triggers(
        data_dir=data_dir,
        test_date="2025-11-21",
        top_longs=TEST_SYMBOLS[:3],   # Test 3 as "LONG candidates"
        top_shorts=TEST_SYMBOLS[3:],  # Test 2 as "SHORT candidates"
    )
