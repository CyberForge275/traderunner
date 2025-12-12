#!/usr/bin/env python3
"""
Demo: Daily Data Loading

Shows how to use DailyDataLoader for strategies.
"""
import asyncio
from datetime import datetime, timedelta

from trading_dashboard.data_loading.loaders.daily_data_loader import DailyDataLoader


def demo_basic_loading():
    """Demo 1: Basic daily data loading."""
    print("=" * 80)
    print("DEMO 1: Basic Daily Data Loading")
    print("=" * 80)
    
    loader = DailyDataLoader()
    
    print(f"\n📂 Data directory: {loader.data_dir}")
    print(f"📅 Available years: {loader.get_available_years()}")
    
    # Load single symbol
    print("\n📊 Loading AAPL (last 30 days)...")
    df = loader.load_data('AAPL', days_back=30)
    
    if not df.empty:
        print(f"  ✅ Loaded {len(df)} days")
        print(f"\n  Sample data:")
        print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].head())
    else:
        print("  ⚠️  No data available (generate with update script)")


def demo_multiple_symbols():
    """Demo 2: Multiple symbols."""
    print("\n" + "=" * 80)
    print("DEMO 2: Multiple Symbols")
    print("=" * 80)
    
    loader = DailyDataLoader()
    
    # Load multiple symbols
    symbols = ['AAPL', 'TSLA', 'MSFT']
    print(f"\n📊 Loading {len(symbols)} symbols...")
    
    df = loader.load_data(
        symbols,
        start_date='2024-01-01',
        end_date='2024-12-31'
    )
    
    if not df.empty:
        print(f"  ✅ Loaded {len(df)} total candles")
        for symbol in symbols:
            count = len(df[df['symbol'] == symbol])
            print(f"     {symbol}: {count} days")
    else:
        print("  ⚠️  No data available")


def demo_metadata():
    """Demo 3: Metadata queries."""
    print("\n" + "=" * 80)
    print("DEMO 3: Metadata Queries")
    print("=" * 80)
    
    loader = DailyDataLoader()
    
    # Get available symbols for current year
    year = datetime.now().year
    print(f"\n📋 Available symbols ({year}):")
    
    symbols = loader.get_available_symbols(year)
    if symbols:
        print(f"  Total: {len(symbols)}")
        print(f"  Sample: {', '.join(symbols[:10])}")
    else:
        print("  ⚠️  No symbols available")
    
    # Get latest update
    latest = loader.get_latest_update(year)
    if latest:
        print(f"\n🕐 Latest data: {latest.date()}")
        days_old = (datetime.now() - latest).days
        print(f"   Age: {days_old} days")
    else:
        print("\n⚠️  No latest data found")


def demo_integration_with_intraday():
    """Demo 4: Combining daily + intraday."""
    print("\n" + "=" * 80)
    print("DEMO 4: Daily + Intraday Integration")
    print("=" * 80)
    
    daily_loader = DailyDataLoader()
    
    print("\n💡 Use Case: Trend filter for InsideBar")
    print("-" * 80)
    
    symbol = 'AAPL'
    
    # Get daily trend (last 20 days)
    daily_df = daily_loader.load_data(symbol, days_back=20)
    
    if not daily_df.empty:
        # Calculate simple trend (close > 20-day MA)
        daily_df['ma20'] = daily_df['close'].rolling(20).mean()
        
        is_uptrend = daily_df['close'].iloc[-1] > daily_df['ma20'].iloc[-1]
        
        print(f"\n  Symbol: {symbol}")
        print(f"  Daily Close: ${daily_df['close'].iloc[-1]:.2f}")
        print(f"  20-day MA: ${daily_df['ma20'].iloc[-1]:.2f}")
        print(f"  Trend: {'📈 UPTREND' if is_uptrend else '📉 DOWNTREND'}")
        print(f"\n  💡 Strategy: Only trade InsideBar breakouts in trend direction")
    else:
        print("  ⚠️  No daily data available")


def main():
    """Run all demos."""
    print("\n" + "🚀" * 40)
    print("Daily Data Loader - Demo")
    print("🚀" * 40)
    
    try:
        demo_basic_loading()
        demo_multiple_symbols()
        demo_metadata()
        demo_integration_with_intraday()
        
        print("\n" + "=" * 80)
        print("✅ All demos completed!")
        print("=" * 80)
        
        print("\n📝 Next steps:")
        print("  1. Generate universe parquet: python scripts/update_daily_data.py --auto")
        print("  2. Setup cron job for daily updates (see scripts/cron.d/daily_data_update)")
        print("  3. Integrate with InsideBar strategy")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
