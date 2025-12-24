#!/usr/bin/env python3
"""
INT Smoke Run - Post-Phase-5 Validation

Creates a fresh TSLA backtest run using Phase 5 code (validity filtering).
This run will demonstrate:
- No zero-duration orders (filtered by Phase 5)
- strategy_policy in diagnostics.json
- Session compliance
- First-IB-per-session semantics
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from axiom_bt.full_backtest_runner import run_backtest_full
from datetime import datetime

# Run configuration
RUN_ID = f"INT_SMOKE_TSLA_PHASE5_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

print(f"=" * 80)
print(f"INT SMOKE RUN - Post-Phase-5 Validation")
print(f"=" * 80)
print(f"Run ID: {RUN_ID}")
print(f"Symbol: TSLA")
print(f"Period: 10 days ending 2024-12-01")
print(f"Strategy: inside_bar (SSOT)")
print(f"=" * 80)
print()

try:
    result = run_backtest_full(
        run_id=RUN_ID,
        symbol="TSLA",
        timeframe="M5",
        requested_end="2024-12-01",
        lookback_days=10,
        strategy_key="inside_bar",
        strategy_params={
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
        },
        artifacts_root=Path("artifacts/backtests"),
        market_tz="America/New_York",
        initial_cash=100000.0,
        costs={"fees_bps": 0.0, "slippage_bps": 0.0},
        debug_trace=True,
    )

    print(f"\n✅ Run completed successfully!")
    print(f"   Run ID: {result.run_id}")
    print(f"   Status: {result.status}")
    print(f"   Path: {result.run_path}")

    # Save run info for validation
    import json
    with open("/tmp/int_smoke_run_info.json", "w") as f:
        json.dump({
            "run_id": result.run_id,
            "run_path": str(result.run_path),
            "status": str(result.status),
            "timestamp": datetime.now().isoformat(),
        }, f, indent=2)

    print(f"\n✅ Run info saved to /tmp/int_smoke_run_info.json")
    print(f"\nNext: Run validation on {result.run_path}")

except Exception as e:
    print(f"\n❌ Run failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
