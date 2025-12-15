#!/usr/bin/env python3
"""
Verify intraday data freshness for all symbols in EODHD_SYMBOLS.

This script checks what data is actually available via IntradayStore
(the same reader the dashboard uses) and reports freshness metrics.

Usage:
    python scripts/verify_intraday_freshness.py

Output:
    Table showing: SYMBOL | TF | rows | last_ts | age_minutes | tz | file_path | file_mtime
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from axiom_bt.intraday import IntradayStore, Timeframe
    from core.settings.intraday_paths import get_intraday_parquet_path
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you run this from traderunner directory with PYTHONPATH=src:.")
    sys.exit(1)


def get_symbols_from_env():
    """Get symbols from EODHD_SYMBOLS environment variable."""
    symbols_env = os.getenv("EODHD_SYMBOLS")
    if not symbols_env:
        print("⚠️  EODHD_SYMBOLS not set, using default test set")
        return ["AAPL", "MSFT", "TSLA", "PLTR"]
    
    return [s.strip().upper() for s in symbols_env.split(",") if s.strip()]


def check_symbol_timeframe(store, symbol, timeframe_str):
    """Check data availability for one symbol/timeframe combination.
    
    Returns:
        dict with keys: symbol, tf, rows, last_ts, age_minutes, tz, file_path, file_mtime, status
    """
    try:
        # Get file path and mtime
        file_path = get_intraday_parquet_path(symbol, timeframe_str)
        
        if not file_path.exists():
            return {
                "symbol": symbol,
                "tf": timeframe_str,
                "rows": 0,
                "last_ts": None,
                "age_minutes": None,
                "tz": None,
                "file_path": str(file_path),
                "file_mtime": None,
                "status": "❌ FILE_NOT_FOUND"
            }
        
        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        
        # Load via IntradayStore (same as dashboard)
        timeframe = Timeframe(timeframe_str)
        df = store.load(symbol, timeframe=timeframe)
        
        if df.empty:
            return {
                "symbol": symbol,
                "tf": timeframe_str,
                "rows": 0,
                "last_ts": None,
                "age_minutes": None,
                "tz": None,
                "file_path": str(file_path),
                "file_mtime": file_mtime.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "⚠️  EMPTY_DF"
            }
        
        # Get last timestamp
        last_ts = df.index[-1]
        tz_info = getattr(df.index, "tz", None)
        
        # Calculate age
        now = pd.Timestamp.now(tz=tz_info if tz_info else None)
        age = now - last_ts
        age_minutes = age.total_seconds() / 60
        
        # Determine status
        if age_minutes < 5:
            status = "✅ FRESH"
        elif age_minutes < 30:
            status = "⏰ RECENT"
        elif age_minutes < 1440:  # 24 hours
            status = "⚠️  STALE"
        else:
            status = "❌ VERY_STALE"
        
        return {
            "symbol": symbol,
            "tf": timeframe_str,
            "rows": len(df),
            "last_ts": last_ts.strftime("%Y-%m-%d %H:%M:%S %Z") if last_ts else None,
            "age_minutes": f"{age_minutes:.1f}",
            "tz": str(tz_info) if tz_info else "naive",
            "file_path": str(file_path.name),  # Just filename for brevity
            "file_mtime": file_mtime.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status
        }
        
    except Exception as e:
        return {
            "symbol": symbol,
            "tf": timeframe_str,
            "rows": None,
            "last_ts": None,
            "age_minutes": None,
            "tz": None,
            "file_path": None,
            "file_mtime": None,
            "status": f"❌ ERROR: {str(e)[:50]}"
        }


def main():
    print("=" * 120)
    print("📊 Intraday Data Freshness Verification")
    print("=" * 120)
    print()
    
    # Get symbols from ENV
    symbols = get_symbols_from_env()
    print(f"Checking {len(symbols)} symbols: {', '.join(symbols)}")
    print(f"Source: EODHD_SYMBOLS environment variable")
    print()
    
    # Initialize IntradayStore
    store = IntradayStore()
    
    # Check all symbols for M1 and M5
    timeframes = ["M1", "M5"]
    results = []
    
    for symbol in symbols:
        for tf in timeframes:
            result = check_symbol_timeframe(store, symbol, tf)
            results.append(result)
    
    # Print results table
    print(f"{'SYMBOL':<8} | {'TF':<4} | {'ROWS':>7} | {'LAST_TS':<25} | {'AGE_MIN':>8} | {'TZ':<20} | {'FILE':<20} | {'MTIME':<20} | {'STATUS':<20}")
    print("-" * 120)
    
    for r in results:
        symbol = r['symbol']
        tf = r['tf']
        rows = r['rows'] if r['rows'] is not None else "N/A"
        last_ts = r['last_ts'] if r['last_ts'] else "N/A"
        age = r['age_minutes'] if r['age_minutes'] else "N/A"
        tz = r['tz'] if r['tz'] else "N/A"
        file_name = r['file_path'] if r['file_path'] else "N/A"
        mtime = r['file_mtime'] if r['file_mtime'] else "N/A"
        status = r['status']
        
        print(f"{symbol:<8} | {tf:<4} | {str(rows):>7} | {last_ts:<25} | {str(age):>8} | {tz:<20} | {file_name:<20} | {mtime:<20} | {status:<20}")
    
    print()
    print("=" * 120)
    
    # Summary
    fresh_count = sum(1 for r in results if "FRESH" in r['status'])
    stale_count = sum(1 for r in results if "STALE" in r['status'])
    error_count = sum(1 for r in results if "ERROR" in r['status'] or "NOT_FOUND" in r['status'] or "EMPTY" in r['status'])
    
    print(f"Summary: {fresh_count} fresh, {stale_count} stale, {error_count} errors/missing")
    print()
    
    # Identify problematic symbols
    problematic = [r for r in results if "ERROR" in r['status'] or "NOT_FOUND" in r['status'] or "EMPTY" in r['status'] or "VERY_STALE" in r['status']]
    
    if problematic:
        print("⚠️  Problematic Symbol/Timeframe Combinations:")
        for r in problematic:
            print(f"   - {r['symbol']} {r['tf']}: {r['status']}")
        print()
    else:
        print("✅ All symbols have fresh data!")
        print()


if __name__ == "__main__":
    main()
