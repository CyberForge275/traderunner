from pathlib import Path
import pandas as pd

from backtest.services.trade_evidence import generate_trade_evidence, ProofStatus


def test_generate_trade_evidence_proven(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    trades = pd.DataFrame(
        {
            "symbol": ["TSLA"],
            "side": ["BUY"],
            "entry_ts": ["2024-01-01T10:00:00Z"],
            "exit_ts": ["2024-01-01T10:05:00Z"],
            "entry_price": [100.0],
            "exit_price": [101.0],
        }
    )
    trades.to_csv(run_dir / "trades.csv", index=False)

    bars = pd.DataFrame(
        {
            "open": [99.5, 100.5],
            "high": [100.5, 101.5],
            "low": [99.0, 100.0],
            "close": [100.4, 101.0],
        },
        index=pd.to_datetime(["2024-01-01T10:00:00Z", "2024-01-01T10:05:00Z"], utc=True),
    )
    bars_dir = run_dir / "bars"
    bars_dir.mkdir()
    bars.to_parquet(bars_dir / "bars_exec_M5_rth.parquet")

    evidence = generate_trade_evidence(run_dir)
    assert evidence is not None
    assert evidence.loc[0, "proof_status"] == ProofStatus.PROVEN.value
