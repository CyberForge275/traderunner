#!/usr/bin/env python3
"""
Manual Pre-PaperTrade Test Script
Run a pre-papertrading session directly using the adapter
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add paths
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "trading_dashboard"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "apps" / "streamlit"))

from trading_dashboard.services.pre_papertrade_adapter import create_adapter

def main():
    print("=" * 60)
    print("Pre-PaperTrade Manual Test")
    print("=" * 60)
    print()
    
    # Configuration
    replay_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    symbols = ['HOOD', 'PLTR', 'APP', 'INTC', 'TSLA', 'NVDA', 'MU', 'AVGO', 'LRCX', 'WBD']
    
    print(f"Replay Date: {replay_date}")
    print(f"Symbols ({len(symbols)}): {', '.join(symbols)}")
    print(f"Strategy: insidebar_intraday")
    print(f"Timeframe: M5")
    print()
    
    # Create adapter with progress callback
    def progress_callback(msg):
        print(f"  {msg}")
    
    adapter = create_adapter(progress_callback=progress_callback)
    
    # Execute replay
    print("Starting replay...")
    print()
    
    try:
        result = adapter.execute_strategy(
            strategy='insidebar_intraday',
            mode='replay',
            symbols=symbols,
            timeframe='M5',
            replay_date=replay_date
        )
        
        print()
        print("=" * 60)
        print("Result:")
        print(f"  Status: {result.get('status', 'unknown')}")
        print(f"  Message: {result.get('message', 'N/A')}")
        print(f"  Signals Generated: {result.get('signals_generated', 0)}")
        print("=" * 60)
        
        if result.get('status') == 'success':
            print()
            print("✅ Test completed successfully!")
            print()
            print("Next steps:")
            print("1. Check signals in database:")
            print("   sqlite3 /home/mirko/data/workspace/droid/marketdata-stream/data/signals.db")
            print("   SELECT COUNT(*), symbol FROM signals WHERE source='pre_papertrade_replay' GROUP BY symbol;")
            print()
            print("2. Wait for sqlite_bridge to forward signals to API")
            print("   tail -f /tmp/sqlite_bridge.log")
            print()
            print("3. Check order intents in automatictrader-api:")
            print("   sqlite3 /home/mirko/data/workspace/automatictrader-api/data/automatictrader.db")
            print("   SELECT COUNT(*), symbol FROM order_intents GROUP BY symbol;")
        else:
            print()
            print("❌ Test failed!")
            print(f"   Error: {result.get('message', 'Unknown error')}")
            
    except Exception as e:
        print()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
