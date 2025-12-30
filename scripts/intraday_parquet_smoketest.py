#!/usr/bin/env python3
"""Smoke test for intraday parquet storage.

Usage:
    python scripts/intraday_parquet_smoketest.py [SYMBOL] [TIMEFRAME]

Examples:
    python scripts/intraday_parquet_smoketest.py PLTR M5
    python scripts/intraday_parquet_smoketest.py AAPL M1
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from axiom_bt.intraday import IntradayStore, Timeframe
    from core.settings.intraday_paths import get_intraday_parquet_path
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you run this from traderunner directory")
    sys.exit(1)


def main():
    # Parse arguments
    symbol = sys.argv[1] if len(sys.argv) > 1 else "PLTR"
    timeframe_str = sys.argv[2] if len(sys.argv) > 2 else "M5"

    # Map string to Timeframe enum
    timeframe_map = {
        "M1": Timeframe.M1,
        "M5": Timeframe.M5,
        "M15": Timeframe.M15,
    }

    if timeframe_str.upper() not in timeframe_map:
        print(f"❌ Invalid timeframe: {timeframe_str}")
        print(f"   Supported: {', '.join(timeframe_map.keys())}")
        sys.exit(1)

    timeframe = timeframe_map[timeframe_str.upper()]

    print(f"\n🔍 Intraday Parquet Smoke Test")
    print(f"={'=' * 60}\n")
    print(f"Symbol:    {symbol}")
    print(f"Timeframe: {timeframe_str.upper()}")
    print()

    # Get file path
    try:
        file_path = get_intraday_parquet_path(symbol, timeframe_str.upper())
        print(f"📁 Parquet Path: {file_path}")
        print(f"   Exists: {'✅ Yes' if file_path.exists() else '❌ No'}")
        print()
    except Exception as e:
        print(f"❌ Error getting path: {e}")
        sys.exit(1)

    if not file_path.exists():
        print("⚠️  File does not exist - no data written yet")
        print()
        sys.exit(0)

    # Load data via IntradayStore
    try:
        store = IntradayStore()
        df = store.load(symbol, timeframe=timeframe)

        if df.empty:
            print("⚠️  File exists but contains no data")
            sys.exit(0)

        print(f"📊 Data Summary")
        print(f"{'-' * 60}")
        print(f"Total rows: {len(df)}")
        print(f"Date range: {df.index[0]} to {df.index[-1]}")
        print()

        # Show last 5 bars
        print(f"📈 Last 5 Bars")
        print(f"{'-' * 60}")
        last_5 = df.tail(5)

        for ts, row in last_5.iterrows():
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S %Z")
            print(f"{ts_str:30} | O:{row['open']:7.2f} H:{row['high']:7.2f} L:{row['low']:7.2f} C:{row['close']:7.2f} V:{int(row['volume']):,}")

        print()

        # Calculate freshness
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from pytz import timezone as ZoneInfo

        ny_tz = ZoneInfo("America/New_York")
        last_bar = df.index[-1]
        now_ny = datetime.now(ny_tz)

        # Ensure both are timezone-aware and in NY timezone
        if last_bar.tz is None:
            last_bar_ny = last_bar.tz_localize("America/New_York")
        else:
            last_bar_ny = last_bar.astimezone(ny_tz)

        delay = now_ny - last_bar_ny
        delay_minutes = delay.total_seconds() / 60

        print(f"⏰ Freshness Check")
        print(f"{'-' * 60}")
        print(f"Last bar (NY):  {last_bar_ny.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Now (NY):       {now_ny.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Delay:          {delay}")
        print(f"                ({delay_minutes:.1f} minutes)")
        print()

        # Status determination
        if delay_minutes <= 10:
            print("✅ Data is FRESH (<= 10 minutes behind)")
        elif delay_minutes <= 60:
            print("⚠️  Data is slightly stale (10-60 minutes behind)")
        elif delay_minutes <= 1440:  # 24 hours
            print("⚠️  Data is stale (hours old)")
        else:
            print("❌ Data is VERY stale (days old)")

        print()

    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
