from __future__ import annotations

from pathlib import Path

import pandas as pd

from axiom_bt.pipeline.data_fetcher import ensure_and_snapshot_bars


class _ClientStub:
    def __init__(self, *args, **kwargs):
        self.base_url = "http://stub"

    def fetch_daily_dataframe(self, req):
        assert req.universe == "US"
        assert req.symbol == "ALL"
        return {
            "status": "ok",
            "columns": [
                "date",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
                "source",
            ],
            "data": [
                {
                    "date": "2026-01-02T00:00:00",
                    "symbol": "AAPL",
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.05,
                    "adj_close": 1.05,
                    "volume": 1000.0,
                    "source": "mysql.sp_timeseries",
                },
                {
                    "date": "2026-01-02T00:00:00",
                    "symbol": "MSFT",
                    "open": 2.0,
                    "high": 2.1,
                    "low": 1.9,
                    "close": 2.05,
                    "adj_close": 2.05,
                    "volume": 2000.0,
                    "source": "mysql.sp_timeseries",
                },
            ],
        }


def test_data_fetcher_d1_all_uses_daily_dataframe_contract(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("axiom_bt.pipeline.data_fetcher.MarketdataStreamClient", _ClientStub)

    out = ensure_and_snapshot_bars(
        run_dir=tmp_path / "run",
        symbol="ALL",
        timeframe="D1",
        requested_end="2026-01-03",
        lookback_days=10,
        market_tz="America/New_York",
        session_mode="raw",
        daily_universe="US",
        daily_symbol_scope="ALL",
    )

    exec_path = Path(out["exec_path"])
    assert exec_path.exists()
    df = pd.read_parquet(exec_path)
    assert len(df) == 2
    assert sorted(df["symbol"].tolist()) == ["AAPL", "MSFT"]
    assert "timestamp" in df.columns
