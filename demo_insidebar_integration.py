#!/usr/bin/env python3
"""
Demo: InsideBar Strategy with New Data Loading System

This demonstrates complete integration:
1. DatabaseLoader - Loads from DB with EODHD backfill
2. BufferManager - Maintains rolling 50-candle window
3. InsideBarDataLoader - Strategy-specific wrapper
4. InsideBarCore - Signal generation

Requirements:
- market_data.db must exist (from marketdata-stream)
- EODHD_API_KEY environment variable (for backfill)
"""
import asyncio
import pandas as pd
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.strategies.inside_bar.data_loader import InsideBarDataLoader
from src.strategies.inside_bar.core import InsideBarCore, InsideBarConfig


async def demo_inside_bar_integration():
    """Demonstrate complete InsideBar strategy with new data loading."""
    print("=" * 80)
    print("InsideBar Strategy - Complete Integration Demo")
    print("=" * 80)

    symbol = 'APP'
    interval = 'M5'

    # Step 1: Create and initialize data loader
    print(f"\n📊 Step 1: Initialize InsideBarDataLoader for {symbol} {interval}")
    print("-" * 80)

    try:
        loader = InsideBarDataLoader(
            symbol=symbol,
            interval=interval,
            lookback_candles=50,
            backfill_enabled=False  # Disable for demo (avoid API calls)
        )

        print(f"  Created loader: {loader.symbol} {loader.interval}")
        print(f"  Lookback: {loader.lookback_candles} candles")
        print(f"  Database: {loader.db_loader.db_path}")

        # Initialize (loads from DB)
        await loader.initialize()

        # Check status
        status = loader.get_status()
        print(f"\n  ✅ Initialization Status:")
        print(f"     Ready: {loader.is_ready()}")
        print(f"     Buffer size: {status.get('buffer_size', 0)}")
        print(f"     Coverage: {status.get('coverage_pct', 0):.1f}%")

        if not loader.is_ready():
            print("\n  ⚠️  Warning: Loader not ready (insufficient data)")
            print("  This is expected if marketdata-stream hasn't run yet")
            print("  or if there's no data for this symbol/interval in DB")
            return

        # Step 2: Get candles for strategy
        print(f"\n📈 Step 2: Get Candles for Strategy Processing")
        print("-" * 80)

        candles = loader.get_candles()
        print(f"  Retrieved: {len(candles)} candles")
        print(f"  Columns: {list(candles.columns)}")
        print(f"\n  Sample (first 5):")
        print(candles[['timestamp', 'open', 'high', 'low', 'close', 'volume']].head())

        # Step 3: Initialize InsideBar strategy
        print(f"\n🎯 Step 3: Initialize InsideBar Strategy Core")
        print("-" * 80)

        config = InsideBarConfig(
            atr_period=14,
            risk_reward_ratio=2.0,
            min_mother_bar_size=0.5,
            breakout_confirmation=True,
            inside_bar_mode='inclusive'
        )

        print(f"  Config:")
        print(f"    ATR Period: {config.atr_period}")
        print(f"    Risk/Reward: {config.risk_reward_ratio}")
        print(f"    Min Mother Size: {config.min_mother_bar_size}")
        print(f"    Breakout Confirmation: {config.breakout_confirmation}")
        print(f"    Mode: {config.inside_bar_mode}")

        # Create strategy core
        core = InsideBarCore(config)

        print(f"\n  Strategy Metadata:")
        metadata = core.metadata
        print(f"    Name: {metadata['name']}")
        print(f"    Version: {metadata['version']}")
        print(f"    Checksum: {metadata['checksum']}")

        # Step 4: Process data and generate signals
        print(f"\n🚀 Step 4: Process Data and Generate Signals")
        print("-" * 80)

        signals = core.process_data(candles, symbol=symbol)

        print(f"  Signals Generated: {len(signals)}")

        if signals:
            print(f"\n  📋 Signal Details:")
            for i, sig in enumerate(signals, 1):
                print(f"\n  Signal {i}:")
                print(f"    Timestamp: {sig.timestamp}")
                print(f"    Side: {sig.side}")
                print(f"    Entry: ${sig.entry_price:.2f}")
                print(f"    Stop Loss: ${sig.stop_loss:.2f}")
                print(f"    Take Profit: ${sig.take_profit:.2f}")
                print(f"    Risk: ${sig.metadata.get('risk', 0):.2f}")
                print(f"    Reward: ${sig.metadata.get('reward', 0):.2f}")
        else:
            print("  No signals generated (no inside bar breakouts in data)")

        print("\n" + "=" * 80)
        print("✅ InsideBar Integration Demo Complete!")
        print("=" * 80)

        print("\n📝 Summary:")
        print(f"  ✅ DataLoader initialized with {status.get('buffer_size', 0)} candles")
        print(f"  ✅ InsideBar strategy processed data")
        print(f"  ✅ Generated {len(signals)} signals")
        print(f"\n💡 Next steps:")
        print(f"  → Deploy to live trading")
        print(f"  → Monitor RTH filtering (9:30-16:00 ET)")
        print(f"  → Verify backfill works on cold start")

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\nℹ️  The market_data.db file was not found.")
        print("   This is expected if marketdata-stream hasn't been started yet.")
        print("\n📌 To fix:")
        print("   1. Start marketdata-stream to create the database")
        print("   2. Wait for some candles to be written")
        print("   3. Re-run this demo")

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(demo_inside_bar_integration())
