#!/usr/bin/env python3
"""Test backtest to debug Trade Inspector bars persistence."""

from pathlib import Path
from axiom_bt.full_backtest_runner import run_backtest_full
import logging

# Configure logging to see output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

result = run_backtest_full(
    run_id='test_trade_inspector_251223',
    symbol='IONQ',
    timeframe='M5',
    requested_end='2025-12-19',
    lookback_days=30,  # Shorter for testing
    strategy_key='inside_bar',
    strategy_params={
        'atr_period': 14,
        'min_mother_bar_size': 0.5,
        'breakout_confirmation': True,
        'risk_reward_ratio': 2,
    },
    artifacts_root=Path('artifacts/backtests'),
    debug_trace=True  # Enable debug logging
)

print("\n" + "="*60)
print(f"BACKTEST RESULT: {result.status}")
print("="*60)

# Check if bars directory was created
run_dir = Path('artifacts/backtests/test_trade_inspector_251223')
bars_dir = run_dir / 'bars'

if bars_dir.exists():
    print(f"✅ bars/ directory exists: {bars_dir}")
    parquet_files = list(bars_dir.glob("*.parquet"))
    if parquet_files:
        print(f"✅ Found {len(parquet_files)} parquet files:")
        for f in parquet_files:
            print(f"  - {f.name} ({f.stat().st_size} bytes)")
    else:
        print(f"❌ No parquet files in bars/ directory")
        print(f"   Files present: {list(bars_dir.iterdir())}")
else:
    print(f"❌ bars/ directory NOT created")

print("\nResult details:", result.details if hasattr(result, 'details') else 'N/A')
