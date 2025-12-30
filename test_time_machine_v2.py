#!/usr/bin/env python3
"""Test V2 strategy with additional parameters."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trading_dashboard.services.pre_papertrade_adapter import create_adapter

# Test V2 with V2-specific parameters
adapter = create_adapter(lambda msg: print(f"  {msg}"))

print("=" * 80)
print("Testing InsideBar V2 with V2-specific parameters")
print("=" * 80)
print()

result = adapter.execute_strategy(
    strategy='insidebar_intraday_v2',  # V2
    mode='replay',
    symbols=['AAPL'],
    timeframe='M5',
    replay_date='2025-11-25',
    config_params={
        # V1 parameters
        'atr_period': 14,
        'risk_reward_ratio': 2.5,
        'min_mother_bar_size': 0.5,
        'breakout_confirmation': True,
        'inside_bar_mode': 'inclusive',
        # V2-specific parameters
        'max_master_range_atr_mult': 3.0,
        'min_master_body_ratio': 0.4,
        'execution_lag_bars': 1,
        'stop_distance_cap': 0.02,
    }
)

print()
print("RESULTS:")
print("=" * 80)
print(f"Status: {result.get('status')}")
print(f"Signals Generated: {result.get('signals_generated', 0)}")

if result['status'] == 'completed':
    print("✅ V2 test passed!")
    print(f"Signals: {len(result.get('signals', []))}")
else:
    print("❌ V2 test failed!")
    print(f"Error: {result.get('error')}")
    sys.exit(1)
