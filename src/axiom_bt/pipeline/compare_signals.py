import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import os

# Ensure local source takes precedence and support 'src.' imports
sys.path.insert(0, '.')
sys.path.insert(0, 'src')

from axiom_bt.full_backtest_runner import run_backtest_full
from axiom_bt.pipeline.cli import main as run_new_pipeline

def compare_signals():
    run_id_legacy = f"COMP_LEGACY_{datetime.now().strftime('%y%m%d_%H%M%S')}"
    run_id_new = f"COMP_NEW_{datetime.now().strftime('%y%m%d_%H%M%S')}"
    
    out_dir_legacy = Path("artifacts/backtests") / run_id_legacy
    out_dir_new = Path(f"/tmp/{run_id_new}")
    
    symbol = "HOOD"
    timeframe = "M5"
    end_date = "2026-01-10"
    lookback_days = 40
    
    strategy_params = {
        "atr_period": 15,
        "min_mother_bar_size": 0.5,
        "breakout_confirmation": True,
        "risk_reward_ratio": 2.0,
        "inside_bar_mode": "inclusive",
        "session_timezone": "America/New_York",
        "session_filter": ["09:30-11:00", "14:00-15:00"],
        "timeframe_minutes": 5,
        "valid_from_policy": "signal_ts",
        "order_validity_policy": "session_end",
        "lookback_candles": 50,
        "max_pattern_age_candles": 12,
        "max_deviation_atr": 3.0,
        "symbol": symbol,
        "timeframe": timeframe,
    }

    print("\n" + "="*70)
    print("RUNNING LEGACY BACKTEST...")
    print("="*70)
    
    os.environ['AXIOM_BT_SKIP_PRECONDITIONS'] = '1'
    
    legacy_res = run_backtest_full(
        run_id=run_id_legacy,
        symbol=symbol,
        timeframe=timeframe,
        requested_end=end_date,
        lookback_days=lookback_days,
        strategy_key="inside_bar",
        strategy_params=strategy_params,
        artifacts_root=Path("artifacts/backtests"),
        market_tz="America/New_York",
    )
    
    legacy_orders_path = out_dir_legacy / "orders.csv"
    if not legacy_orders_path.exists():
        print("❌ Legacy orders.csv not found!")
        return

    legacy_orders = pd.read_csv(legacy_orders_path)
    # Legacy uses 'created_from_ts' or 'valid_from'
    legacy_orders['ts'] = pd.to_datetime(legacy_orders['valid_from'], utc=True)
    legacy_orders = legacy_orders[['ts', 'side']].sort_values('ts').reset_index(drop=True)

    print(f"Legacy signals: {len(legacy_orders)}")

    print("\n" + "="*70)
    print("RUNNING NEW PIPELINE...")
    print("="*70)
    
    # Use the bars path from the legacy run to ensure they use the same data
    # legacy_res might contain the path, but let's look for it
    bars_path = out_dir_legacy / "bars" / "bars_exec_M5_rth.parquet"
    if not bars_path.exists():
        # fallback to find it
        bars_path = list((out_dir_legacy / "bars").glob("bars_exec_*_rth.parquet"))[0]
    
    print(f"Using bars: {bars_path}")

    argv = [
        "--run-id", run_id_new,
        "--out-dir", str(out_dir_new),
        "--bars-path", str(bars_path),
        "--strategy-id", "insidebar_intraday",
        "--strategy-version", "1.0.0",
        "--symbol", symbol,
        "--timeframe", timeframe,
        "--valid-to", end_date,
        "--lookback-days", str(lookback_days),
        "--initial-cash", "100000",
        "--compound-enabled",
        "--fees-bps", "0",
        "--slippage-bps", "0",
    ]
    run_new_pipeline(argv)
    
    new_intent_path = out_dir_new / "events_intent.csv"
    if not new_intent_path.exists():
        print("❌ New pipeline intent.csv not found!")
        return
        
    new_intent = pd.read_csv(new_intent_path)
    new_intent['ts'] = pd.to_datetime(new_intent['signal_ts'], utc=True)
    new_intent = new_intent[['ts', 'side']].sort_values('ts').reset_index(drop=True)

    print(f"New pipeline signals: {len(new_intent)}")

    print("\n" + "="*70)
    print("COMPARISON RESULTS")
    print("="*70)
    
    if len(legacy_orders) != len(new_intent):
        print(f"❌ SIGNAL COUNT MISMATCH: Legacy={len(legacy_orders)}, New={len(new_intent)}")
    
    # Compare timestamps and sides
    merged = pd.merge(legacy_orders, new_intent, on='ts', how='outer', suffixes=('_legacy', '_new'))
    mismatches = merged[merged['side_legacy'] != merged['side_new']]
    
    if mismatches.empty:
        print("✅ ALL SIGNALS MATCH PERFECTLY (Timestamp & Side)")
    else:
        print(f"❌ MISMATCHES FOUND: {len(mismatches)}")
        print(mismatches.head(10))

if __name__ == "__main__":
    compare_signals()
