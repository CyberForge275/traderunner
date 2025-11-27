#!/usr/bin/env python3
"""Run Rudometkin (RK) strategy for multiple dates with daily lists and intraday signals."""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from axiom_bt.daily import DailySpec, DailyStore, DailySourceType
from axiom_bt.intraday import IntradayStore, IntradaySpec, Timeframe
from strategies.rudometkin_moc.strategy import RudometkinMOCStrategy


def run_daily_scan(universe_path: str, target_date: str, max_candidates: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """Run daily scan for a specific date and return candidates."""
    
    print(f"\n{'='*100}")
    print(f"📅 DAILY SCAN FOR {target_date}")
    print(f"{'='*100}")
    
    # Load universe via central DailyStore
    store = DailyStore(default_tz="America/New_York")
    spec = DailySpec(
        symbols=[],
        start=target_date,
        end=target_date,
        tz="America/New_York",
        source_type=DailySourceType.UNIVERSE,
        universe_path=Path(universe_path),
    )

    df = store.load_window(spec, lookback_days=300)

    if df.empty:
        print(f"❌ No data found for {target_date} with 300-day lookback")
        return [], []

    # Filter with 300-day lookback buffer (already applied in load_window)
    target_dt = pd.Timestamp(target_date)
    historical_data = df.copy()
    
    # Get symbols that have data on the target date
    target_day_symbols = historical_data[
        historical_data["timestamp"].dt.date == target_dt.date()
    ]["symbol"].unique()
    
    print(f"📊 Scanning {len(target_day_symbols)} symbols...")
    
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
        "max_daily_signals": max_candidates,
    }
    
    # Initialize strategy
    strategy = RudometkinMOCStrategy()
    
    # Track results
    long_candidates = []
    short_candidates = []
    
    for symbol in target_day_symbols:
        symbol_data = historical_data[historical_data["symbol"] == symbol].copy()
        symbol_data = symbol_data[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        
        try:
            signals = strategy.generate_signals(symbol_data, symbol, config)
            
            if signals:
                for sig in signals:
                    score = sig.metadata.get("score", 0)
                    setup = sig.metadata.get("setup", "unknown")
                    
                    candidate = {
                        "symbol": symbol,
                        "score": score,
                        "setup": setup,
                        "entry": sig.entry_price,
                        "signal": sig
                    }
                    
                    if sig.signal_type.upper() == "LONG":
                        long_candidates.append(candidate)
                    elif sig.signal_type.upper() == "SHORT":
                        short_candidates.append(candidate)
        except Exception:
            pass
    
    # Sort by score (descending)
    long_candidates.sort(key=lambda x: x["score"], reverse=True)
    short_candidates.sort(key=lambda x: x["score"], reverse=True)
    
    # Limit to max_candidates
    long_candidates = long_candidates[:max_candidates]
    short_candidates = short_candidates[:max_candidates]
    
    # Display results
    print(f"\n🟢 LONG CANDIDATES: {len(long_candidates)}")
    print("-" * 100)
    if long_candidates:
        print(f"{'Rank':<5} {'Symbol':<10} {'Score':<12} {'Entry Price':<12} {'Setup':<15}")
        print("-" * 100)
        for i, cand in enumerate(long_candidates, 1):
            print(f"{i:<5} {cand['symbol']:<10} {cand['score']:<12.4f} ${cand['entry']:<11.2f} {cand['setup']:<15}")
    else:
        print("  No LONG candidates found")
    
    print(f"\n🔴 SHORT CANDIDATES: {len(short_candidates)}")
    print("-" * 100)
    if short_candidates:
        print(f"{'Rank':<5} {'Symbol':<10} {'Score':<12} {'Entry Price':<12} {'Setup':<15}")
        print("-" * 100)
        for i, cand in enumerate(short_candidates, 1):
            print(f"{i:<5} {cand['symbol']:<10} {cand['score']:<12.4f} ${cand['entry']:<11.2f} {cand['setup']:<15}")
    else:
        print("  No SHORT candidates found")
    
    return long_candidates, short_candidates


def check_intraday_signals(
    data_dir: Path,
    target_date: str,
    long_candidates: List[Dict],
    short_candidates: List[Dict]
) -> Dict:
    """Check if daily candidates triggered intraday signals."""
    
    print(f"\n{'='*100}")
    print(f"🔍 INTRADAY SIGNALS CHECK FOR {target_date}")
    print(f"{'='*100}")
    
    if not data_dir.exists():
        print(f"⚠️  Intraday data directory not found: {data_dir}")
        print("  Skipping intraday signal check")
        return {"long": [], "short": []}
    
    strategy = RudometkinMOCStrategy()
    store = IntradayStore(default_tz="America/New_York")
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
    
    target_ts = pd.Timestamp(target_date)
    
    # Check LONG candidates
    long_signals = []
    if long_candidates:
        print(f"\n🟢 Checking {len(long_candidates)} LONG candidates for intraday triggers...")
        print("-" * 100)
        for cand in long_candidates:
            result = _check_symbol_intraday(
                strategy, cand["symbol"], data_dir, target_ts, config, "LONG"
            )
            if result:
                long_signals.append({**cand, "intraday_signals": result})
    
    # Check SHORT candidates  
    short_signals = []
    if short_candidates:
        print(f"\n🔴 Checking {len(short_candidates)} SHORT candidates for intraday triggers...")
        print("-" * 100)
        for cand in short_candidates:
            result = _check_symbol_intraday(
                strategy, cand["symbol"], data_dir, target_ts, config, "SHORT"
            )
            if result:
                short_signals.append({**cand, "intraday_signals": result})
    
    # Summary
    print(f"\n📊 INTRADAY SUMMARY:")
    print(f"  LONG candidates with signals:  {len(long_signals)}/{len(long_candidates)}")
    print(f"  SHORT candidates with signals: {len(short_signals)}/{len(short_candidates)}")
    
    return {"long": long_signals, "short": short_signals}


def _check_symbol_intraday(
    strategy,
    symbol: str,
    data_dir: Path,
    target_date: pd.Timestamp,
    config: dict,
    expected_direction: str,
) -> List:
    """Check one symbol for intraday signals."""
    
    store = IntradayStore(default_tz="America/New_York")

    try:
        df = store.load(symbol, timeframe=Timeframe.M5)

        if df.index.tz is not None:
            tz = df.index.tz
            lookback_start = (target_date - pd.Timedelta(days=300)).tz_localize(tz)
            target_end = (target_date + pd.Timedelta(days=1)).tz_localize(tz)
        else:
            lookback_start = target_date - pd.Timedelta(days=300)
            target_end = target_date + pd.Timedelta(days=1)

        df_filtered = df[
            (df.index >= lookback_start) &
            (df.index <= target_end)
        ].copy()
        
        if df_filtered.empty or len(df_filtered) < 200:
            print(f"  {symbol:<10} ⚠️  Insufficient data")
            return []
        
        # Standardize columns
        df_filtered = df_filtered.reset_index().rename(columns={"timestamp": "timestamp"})
        
        # Generate signals
        signals = strategy.generate_signals(df_filtered, symbol, config)
        
        if not signals:
            print(f"  {symbol:<10} ⚪ No signals")
            return []
        
        # Filter to target date
        target_day_signals = [
            s for s in signals
            if pd.Timestamp(s.timestamp).date() == target_date.date()
        ]
        
        if not target_day_signals:
            print(f"  {symbol:<10} ⚪ No signals on target date")
            return []
        
        # Display results
        print(f"  {symbol:<10} ✅ {len(target_day_signals)} signal(s)")
        
        # Calculate MOC exit (close of the last bar of the day)
        day_data = df_filtered[df_filtered["timestamp"].dt.date == target_date.date()]
        if not day_data.empty:
            exit_price = day_data.iloc[-1]["close"]
        else:
            exit_price = 0.0
            
        for sig in target_day_signals[:2]:
            sig_time = pd.Timestamp(sig.timestamp)
            print(f"               ↳ Entry: {sig_time.strftime('%H:%M')} @ ${sig.entry_price:.2f}")
            print(f"               ↳ Exit:  MOC   @ ${exit_price:.2f}")
        
        return target_day_signals
        
    except Exception as e:
        print(f"  {symbol:<10} ❌ Error: {type(e).__name__}")
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Run Rudometkin (RK) strategy for multiple dates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run for last 3 days (default)
  python run_rk_strategy.py
  
  # Run for last 5 days
  python run_rk_strategy.py --days 5
  
  # Specify custom universe and intraday data
  python run_rk_strategy.py --universe data/universe/rudometkin.parquet --intraday artifacts/data_m5
  
  # Show top 10 candidates per direction
  python run_rk_strategy.py --max-candidates 10
        """
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Number of previous trading days to analyze (default: 3)"
    )
    
    parser.add_argument(
        "--universe",
        type=str,
        default="data/universe/rudometkin.parquet",
        help="Path to universe parquet file"
    )
    
    parser.add_argument(
        "--intraday",
        type=str,
        default="artifacts/data_m5",
        help="Path to intraday data directory (M5 bars)"
    )
    
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=20,
        help="Maximum candidates to show per direction (default: 20)"
    )
    
    parser.add_argument(
        "--skip-intraday",
        action="store_true",
        help="Skip intraday signal check"
    )
    
    args = parser.parse_args()
    
    # Validate paths
    universe_path = Path(args.universe)
    if not universe_path.exists():
        print(f"❌ Universe file not found: {universe_path}")
        return 1
    
    intraday_dir = Path(args.intraday)
    
    # Get the most recent date from the universe data
    universe_df = pd.read_parquet(universe_path)
    if "Date" in universe_df.columns:
        universe_df["Date"] = pd.to_datetime(universe_df["Date"])
        most_recent_date = universe_df["Date"].max().date()
    else:
        print(f"❌ No 'Date' column found in universe file")
        return 1
    
    # Calculate dates - get last N trading days (excluding weekends) from most recent available date
    dates = []
    current_date = most_recent_date
    
    while len(dates) < args.days:
        # Skip weekends
        if current_date.weekday() < 5:  # Monday=0, Friday=4
            dates.append(current_date)
        current_date -= timedelta(days=1)
    
    dates.reverse()  # Chronological order
    
    print("=" * 100)
    print(f"🚀 RUDOMETKIN (RK) STRATEGY CLI")
    print("=" * 100)
    print(f"📅 Analyzing {args.days} trading days: {dates[0]} to {dates[-1]}")
    print(f"📁 Universe: {universe_path}")
    print(f"📁 Intraday: {intraday_dir}")
    print(f"🎯 Max candidates per direction: {args.max_candidates}")
    
    # Run analysis for each date
    all_results = {}
    
    # First pass: Run daily scans and collect candidates
    print(f"\n🚀 PHASE 1: Running Daily Scans...")
    daily_candidates = {} # date -> (longs, shorts)
    all_symbols_to_fetch = set()
    
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        
        # Run daily scan
        long_cands, short_cands = run_daily_scan(
            str(universe_path),
            date_str,
            max_candidates=args.max_candidates
        )
        
        daily_candidates[date_str] = (long_cands, short_cands)
        
        for c in long_cands:
            all_symbols_to_fetch.add(c["symbol"])
        for c in short_cands:
            all_symbols_to_fetch.add(c["symbol"])

    # Phase 2: Ensure Intraday Data
    if not args.skip_intraday and all_symbols_to_fetch:
        print(f"\n🚀 PHASE 2: Ensuring Intraday Data for {len(all_symbols_to_fetch)} symbols...")
        print("-" * 100)
        
        try:
            store = IntradayStore()
            # Ensure data covers the whole analysis period plus lookback
            # Using a safe buffer of 15 days before the first analysis date
            start_fetch = dates[0] - timedelta(days=15)
            end_fetch = dates[-1] + timedelta(days=1) # Include the last day
            
            spec = IntradaySpec(
                symbols=list(all_symbols_to_fetch),
                start=start_fetch,
                end=end_fetch,
                timeframe=Timeframe.M5, # Default to M5 as requested
            )
            
            actions = store.ensure(spec)
            
            # Summary of actions
            fetched = sum(1 for acts in actions.values() if "fetch_m1" in acts)
            cached = sum(1 for acts in actions.values() if "use_cached_m1" in acts)
            print(f"✅ Data check complete: {fetched} fetched, {cached} used cache")
            
        except Exception as e:
            print(f"❌ Error ensuring intraday data: {e}")
            print("   Continuing with available data...")

    # Phase 3: Check Intraday Signals
    print(f"\n🚀 PHASE 3: Checking Intraday Signals...")
    
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        long_cands, short_cands = daily_candidates[date_str]
        
        # Check intraday signals
        intraday_results = {"long": [], "short": []}
        if not args.skip_intraday and (long_cands or short_cands):
            intraday_results = check_intraday_signals(
                intraday_dir, # This arg is now ignored by check_intraday_signals but kept for signature
                date_str,
                long_cands,
                short_cands
            )
        
        all_results[date_str] = {
            "long_candidates": long_cands,
            "short_candidates": short_cands,
            "intraday": intraday_results
        }
    
    # Final summary
    print(f"\n{'='*100}")
    print("📈 OVERALL SUMMARY")
    print(f"{'='*100}")
    
    for date_str, results in all_results.items():
        long_count = len(results["long_candidates"])
        short_count = len(results["short_candidates"])
        long_intraday = len(results["intraday"]["long"])
        short_intraday = len(results["intraday"]["short"])
        
        print(f"\n{date_str}:")
        print(f"  Daily:    {long_count} LONG, {short_count} SHORT")
        if not args.skip_intraday:
            print(f"  Intraday: {long_intraday} LONG triggered, {short_intraday} SHORT triggered")
    
    print(f"\n{'='*100}")
    print("✅ Analysis complete!")
    print(f"{'='*100}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
