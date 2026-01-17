import pandas as pd
from pathlib import Path
import pytest
from src.axiom_bt.compat.trades_contract import REQUIRED_UI_COLUMNS

ARTIFACTS_DIR = Path("artifacts/backtests")

def get_recent_runs(limit=5):
    """Get the most recent backtest run directories."""
    if not ARTIFACTS_DIR.exists():
        return []
    
    # Sort by modification time (most recent first)
    runs = sorted(
        [d for d in ARTIFACTS_DIR.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )
    return runs[:limit]

@pytest.mark.parametrize("run_dir", get_recent_runs(limit=10))
def test_all_artifacts_in_recent_runs_must_follow_contract(run_dir):
    """
    Architecture Test: Verify that trades.csv, equity_curve.csv, 
    and filled_orders.csv follow the UI contract.
    """
    # 1. trades.csv
    trades_path = run_dir / "trades.csv"
    if trades_path.exists():
        df = pd.read_csv(trades_path)
        missing = [c for c in REQUIRED_UI_COLUMNS if c not in df.columns]
        assert not missing, f"Run {run_dir.name} has invalid trades.csv. Missing: {missing}"

    # 2. equity_curve.csv
    equity_path = run_dir / "equity_curve.csv"
    if equity_path.exists():
        df = pd.read_csv(equity_path)
        required_equity = ["ts", "equity", "drawdown_pct"]
        missing = [c for c in required_equity if c not in df.columns]
        assert not missing, f"Run {run_dir.name} has invalid equity_curve.csv. Missing: {missing}"

    # 3. filled_orders.csv
    fills_path = run_dir / "filled_orders.csv"
    if fills_path.exists():
        df = pd.read_csv(fills_path)
        missing = [c for c in REQUIRED_UI_COLUMNS if c not in df.columns]
        assert not missing, f"Run {run_dir.name} has invalid filled_orders.csv. Missing: {missing}"

def test_no_rogue_trade_writers():
    """
    Placeholder for a static analysis test if needed.
    For now, we rely on the integration tests.
    """
    pass
