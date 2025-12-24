from pathlib import Path
import pandas as pd

from trading_dashboard.repositories.trade_repository import TradeRepository


def test_load_all(tmp_path: Path):
    run_dir = tmp_path / "run1"
    run_dir.mkdir(parents=True)
    (run_dir / "trades.csv").write_text("symbol,entry_ts,entry_price,exit_ts,exit_price\nTSLA,2024-01-01T10:00:00Z,100,2024-01-01T10:05:00Z,101")
    (run_dir / "orders.csv").write_text("order_id,signal_id\n1,abc")
    (run_dir / "trade_evidence.csv").write_text("trade_id,proof_status\n0,PROVEN")
    bars_dir = run_dir / "bars"
    bars_dir.mkdir()
    df = pd.DataFrame({"open": [1], "high": [2], "low": [0.5], "close": [1.5]}, index=pd.to_datetime(["2024-01-01T10:00:00Z"], utc=True))
    df.to_parquet(bars_dir / "bars_exec_M5_rth.parquet")

    repo = TradeRepository(artifacts_root=tmp_path)
    artifacts = repo.load_all("run1")
    assert artifacts.trades is not None
    assert len(artifacts.trades) == 1
    assert artifacts.bars_exec is not None
