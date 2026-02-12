from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_data_fetcher_reads_marketdata_root_from_runtime_config(tmp_path: Path, monkeypatch):
    from core.settings.runtime_config import reset_runtime_config_for_tests
    from axiom_bt.pipeline.data_fetcher import ensure_and_snapshot_bars

    cfg = tmp_path / "trading.yaml"
    data_root = tmp_path / "marketdata"
    cfg.write_text(
        f"""
paths:
  marketdata_data_root: {data_root}
  trading_artifacts_root: {tmp_path / 'artifacts'}
""".strip()
    )

    derived = data_root / "derived" / "tf_m5" / "HOOD.parquet"
    derived.parent.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp("2026-01-13 14:30:00", tz="UTC")
    df = pd.DataFrame(
        {
            "ts": [int((ts + pd.Timedelta(minutes=5 * i)).timestamp()) for i in range(20)],
            "open": [10 + i for i in range(20)],
            "high": [11 + i for i in range(20)],
            "low": [9 + i for i in range(20)],
            "close": [10.5 + i for i in range(20)],
            "volume": [100 + i for i in range(20)],
        }
    )
    df.to_parquet(derived)

    monkeypatch.setenv("TRADING_CONFIG", str(cfg))
    monkeypatch.delenv("MARKETDATA_DATA_ROOT", raising=False)
    reset_runtime_config_for_tests()

    out = ensure_and_snapshot_bars(
        run_dir=tmp_path / "run",
        symbol="HOOD",
        timeframe="M5",
        requested_end="2026-01-14",
        lookback_days=1,
        market_tz="America/New_York",
    )

    assert Path(out["exec_path"]).exists()
