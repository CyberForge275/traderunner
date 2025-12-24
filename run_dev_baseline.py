#!/usr/bin/env python3
"""
Local DEV baseline run - Same config as INT for comparison.
"""
import sys
sys.path.insert(0, 'src')

import os
from pathlib import Path
from datetime import datetime

# Skip coverage gate for local testing
os.environ['AXIOM_BT_SKIP_PRECONDITIONS'] = '1'

from axiom_bt.full_backtest_runner import run_backtest_full

# Match INT config exactly
config = {
    "atr_period": 14,
    "min_mother_bar_size": 0.5,
    "breakout_confirmation": True,
    "risk_reward_ratio": 2,
    "lookback_candles": 50,
    "max_pattern_age_candles": 12,
    "execution_lag": 0,
    "session_timezone": "America/New_York",
    "session_filter": ["10:00-11:00", "14:00-15:00"],
    "order_validity_policy": "one_bar",
    "timeframe_minutes": 5,
    "valid_from_policy": "signal_ts",
}

# Data config  
end_date = "2025-12-18"
lookback_days = 6
artifacts_root = Path("artifacts/backtests")
run_id = f"DEV_{datetime.now().strftime('%y%m%d_%H%M%S')}_HOOD_baseline"

print("=" * 70)
print("LOCAL DEV BASELINE RUN")
print("=" * 70)
print(f"Run ID: {run_id}")
print(f"Session Filter: {config['session_filter']} ({config['session_timezone']})")
print(f"Output: {artifacts_root / run_id}")
print("=" * 70)

try:
    result = run_backtest_full(
        run_id=run_id,
        strategy_key="inside_bar",
        symbols=["HOOD"],
        timeframe="M5",
        requested_end=end_date,
        lookback_days=lookback_days,
        strategy_params=config,
        artifacts_root=artifacts_root,
        market_tz="America/New_York",
    )
    
    print("\n" + "=" * 70)
    print("RUN COMPLETED")
    print("=" * 70)
    print(f"Status: {result.get('status', 'UNKNOWN')}")
    print(f"Run ID: {result.get('run_id', run_id)}")
    print(f"Artifacts: {artifacts_root / run_id}")
    
    # Check for orders
    orders_path = artifacts_root / run_id / "orders.csv"
    if orders_path.exists():
        import pandas as pd
        orders = pd.read_csv(orders_path)
        print(f"\n✅ Orders generated: {len(orders)}")
        print(f"   Columns: {list(orders.columns)}")
        if len(orders) > 0:
            print(f"\n   First 5 orders:")
            print(orders[['valid_from', 'symbol', 'side', 'NY_time']].head())
    else:
        print("\n⚠️  No orders.csv generated")
    
    print("\n" + "=" * 70)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
