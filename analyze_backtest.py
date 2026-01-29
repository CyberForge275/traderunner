import pandas as pd
import json
from pathlib import Path

def analyze_run(run_dir):
    print(f"Analyzing {run_dir}")
    
    intents = pd.read_csv(run_dir / "events_intent.csv")
    fills = pd.read_csv(run_dir / "fills.csv")
    trades = pd.read_csv(run_dir / "trades.csv")
    
    # Basic counts
    print(f"Intents: {len(intents)}")
    print(f"Fills: {len(fills)}")
    print(f"Trades: {len(trades)}")
    
    # Check for intent-fill alignment
    missing_fills = intents[~intents['template_id'].isin(fills['template_id'])]
    print(f"Intents without fills: {len(missing_fills)}")
    
    # Analyze trade durations (entry vs exit)
    trades['entry_ts'] = pd.to_datetime(trades['entry_ts'])
    trades['exit_ts'] = pd.to_datetime(trades['exit_ts'])
    trades['duration'] = (trades['exit_ts'] - trades['entry_ts']).dt.total_seconds()
    
    print("\nTrade Duration Stats (seconds):")
    print(trades['duration'].describe())
    
    # Analyze prices
    trades['price_diff'] = trades['exit_price'] - trades['entry_price']
    print("\nPrice Diff Stats:")
    print(trades['price_diff'].describe())
    
    # Verify PnL calculation
    print(f"\nTotal PnL in trades.csv: {trades['pnl'].sum()}")

if __name__ == "__main__":
    run_dir = Path("artifacts/backtest/dev_260114_140916")
    analyze_run(run_dir)
