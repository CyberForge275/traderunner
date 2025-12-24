from pathlib import Path
import pandas as pd

from trading_dashboard.repositories.trade_repository import TradeRepository
from trading_dashboard.services.trade_detail_service import TradeDetailService


def test_trade_detail_service_returns_detail(tmp_path: Path):
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
            "stop_loss": [99.0],
            "take_profit": [102.0],
        }
    )
    trades.to_csv(run_dir / "trades.csv", index=False)
    bars_dir = run_dir / "bars"
    bars_dir.mkdir()
    bars = pd.DataFrame(
        {
            "open": [99.5, 100.5],
            "high": [100.5, 101.5],
            "low": [99.0, 100.0],
            "close": [100.4, 101.0],
        },
        index=pd.to_datetime(["2024-01-01T10:00:00Z", "2024-01-01T10:05:00Z"], utc=True),
    )
    bars.to_parquet(bars_dir / "bars_exec_M5_rth.parquet")

    repo = TradeRepository(artifacts_root=tmp_path)
    service = TradeDetailService(repo)
    detail = service.get_trade_detail("run", 0)
    assert detail is not None
    assert detail.exec_bars is not None
    assert detail.trade_row.get("symbol") == "TSLA"
