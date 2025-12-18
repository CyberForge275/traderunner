#!/usr/bin/env python3
"""
Validation Checkpoint Runner for InsideBar SSOT

Runs TSLA 10-day backtest and validates:
- Fills > 0
- Session compliance (15-17 Berlin)  
- First-IB-per-session semantics
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from axiom_bt.full_backtest_runner import run_backtest_full
from axiom_bt.engines.replay_engine import Costs
from datetime import datetime

# Configuration
symbol = "TSLA"
strategy_key = "inside_bar"
timeframe = "M5"
requested_end = "2024-12-01"
lookback_days = 10

# Strategy parameters (spec-compliant defaults)
strategy_params = {
    "session_timezone": "Europe/Berlin",
    "session_windows": ["15:00-16:00", "16:00-17:00"],
    "max_trades_per_session": 1,
    "entry_level_mode": "mother_bar",
    "order_validity_policy": "session_end",
    "valid_from_policy": "signal_ts",
    "stop_distance_cap_ticks": 40,
    "tick_size": 0.01,
    "trailing_enabled": False,
    "atr_period": 14,
    "risk_reward_ratio": 2.0,
    "min_mother_bar_size": 0.5,
}

# Artifacts root
artifacts_root = Path("artifacts/backtests")
artifacts_root.mkdir(parents=True, exist_ok=True)

print(f"=" * 80)
print(f"InsideBar SSOT Validation Checkpoint")
print(f"=" * 80)
print(f"Symbol: {symbol}")
print(f"Timeframe: {timeframe}")
print(f"Period: {lookback_days} days ending {requested_end}")
print(f"Strategy: {strategy_key} (SSOT)")
print(f"=" * 80)
print()

# Run backtest
print("[1/4] Running backtest...")
try:
    result = run_backtest_full(
        symbol=symbol,
        strategy_key=strategy_key,
        timeframe=timeframe,
        requested_end=requested_end,
        lookback_days=lookback_days,
        strategy_params=strategy_params,
        artifacts_root=artifacts_root,
        market_tz="America/New_York",
        initial_cash=100000.0,
        costs={"fees_bps": 0.0, "slippage_bps": 0.0},
        debug_trace=True,  # Enable tracing for validation
    )
    
    print(f"✅ Backtest completed")
    print(f"   Run ID: {result.run_id}")
    print(f"   Status: {result.status}")
    print(f"   Run Path: {result.run_path}")
    print()
    
    # Save run info for validation script
    import json
    validation_info = {
        "run_id": result.run_id,
        "run_path": str(result.run_path),
        "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "strategy": strategy_key,
        "timeframe": timeframe,
    }
    
    with open("/tmp/validation_run_info.json", "w") as f:
        json.dump(validation_info, f, indent=2)
    
    print(f"✅ Run info saved to /tmp/validation_run_info.json")
    print()
    print(f"Next: Run validation analysis on {result.run_path}")
    
except Exception as e:
    print(f"❌ Backtest failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
