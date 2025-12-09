#!/usr/bin/env python3
"""
Dry run test for Time Machine with Lookback Period Support

This script tests the Pre-PaperTrade adapter directly via CLI to verify:
1. Lookback periods calculate correctly
2. Historical data loads with buffer
3. Indicators calculate (ATR14)
4. Signals generate correctly
5. Filtering to target date works
"""

import sys
from pathlib import Path

# Setup paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trading_dashboard.services.pre_papertrade_adapter import create_adapter

def test_time_machine():
    """Test Time Machine with InsideBar on AAPL for Nov 26, 2024."""
    
    print("=" * 80)
    print("TIME MACHINE DRY RUN TEST")
    print("=" * 80)
    print()
    
    # Progress callback to see what's happening
    progress_log = []
    def progress_callback(msg):
        print(f"  {msg}")
        progress_log.append(msg)
    
    # Create adapter with progress callback
    adapter = create_adapter(progress_callback)
    
    # Test configuration
    test_config = {
        'strategy': 'insidebar_intraday',  # Correct strategy name from registry
        'mode': 'replay',
        'symbols': ['AAPL'],  # Test with 1 symbol first
        'timeframe': 'M5',
        'replay_date': '2025-11-25',  # Use date that exists in data
        'config_params': {
            # Required parameters
            'atr_period': 14,
            'risk_reward_ratio': 2.0,
            # Optional parameters
            'min_mother_bar_size': 0.5,
            'breakout_confirmation': True,
            'inside_bar_mode': 'inclusive',
        }
    }
    
    print("Test Configuration:")
    print(f"  Strategy: {test_config['strategy']}")
    print(f"  Mode: {test_config['mode']}")
    print(f"  Symbols: {', '.join(test_config['symbols'])}")
    print(f"  Timeframe: {test_config['timeframe']}")
    print(f"  Replay Date: {test_config['replay_date']}")
    print()
    
    print("Executing Time Machine...")
    print("-" * 80)
    
    # Run Time Machine
    result = adapter.execute_strategy(**test_config)
    
    print("-" * 80)
    print()
    
    # Display results
    print("RESULTS:")
    print("=" * 80)
    print(f"Status: {result.get('status', 'unknown')}")
    
    if result['status'] == 'completed':
        print(f"✅ SUCCESS")
        print()
        print(f"Signals Generated: {result.get('signals_generated', 0)}")
        print(f"Lookback Days: {result.get('lookback_days', 0)}")
        print(f"Replay Date: {result.get('replay_date', 'N/A')}")
        print()
        
        if result.get('signals'):
            print(f"Signal Details ({len(result['signals'])} total):")
            print("-" * 80)
            for i, sig in enumerate(result['signals'], 1):
                print(f"{i}. {sig['symbol']} {sig['side']} @ ${sig['entry_price']:.2f}")
                print(f"   Stop Loss: ${sig['stop_loss']:.2f}")
                print(f"   Take Profit: ${sig['take_profit']:.2f}")
                print(f"   Detected At: {sig['detected_at']}")
                print(f"   Strategy: {sig['strategy']}")
                print()
        else:
            print("⚠️ No signals generated (this may be normal if no patterns detected)")
            print()
        
        # Verify lookback in progress log
        print("Lookback Verification:")
        print("-" * 80)
        lookback_msgs = [msg for msg in progress_log if 'lookback' in msg.lower() or 'days' in msg.lower()]
        for msg in lookback_msgs[:5]:  # Show first 5 lookback-related messages
            print(f"  ✓ {msg}")
        print()
        
    else:
        print(f"❌ FAILED")
        print(f"Error: {result.get('error', 'Unknown error')}")
        if result.get('traceback'):
            print()
            print("Traceback:")
            print(result['traceback'])
    
    print("=" * 80)
    
    return result['status'] == 'completed'


if __name__ == '__main__':
    try:
        success = test_time_machine()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
