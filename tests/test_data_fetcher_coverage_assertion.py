from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from axiom_bt.pipeline.data_fetcher import MissingHistoricalDataError, ensure_and_snapshot_bars


def _write_derived_m5(path: Path, start: str, end: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range(start=start, end=end, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "ts": (idx.view("int64") // 10**9).astype("int64"),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
        }
    )
    df.to_parquet(path)


def test_consumer_does_not_fail_when_producer_ok_even_if_local_bounds_short(monkeypatch, tmp_path: Path):
    from core.settings.runtime_config import reset_runtime_config_for_tests

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        f"""
paths:
  marketdata_data_root: {tmp_path}
  trading_artifacts_root: {tmp_path / "artifacts"}
""".strip()
    )
    reset_runtime_config_for_tests()
    monkeypatch.setenv("TRADING_CONFIG", str(cfg))

    # Local file does not reach requested_end, but consumer must not apply its own gap semantics.
    _write_derived_m5(
        tmp_path / "derived" / "tf_m5" / "HOOD.parquet",
        start="2026-02-01 14:30:00",
        end="2026-02-13 19:55:00",
    )

    out = ensure_and_snapshot_bars(
        run_dir=tmp_path / "run",
        symbol="HOOD",
        timeframe="M5",
        requested_end="2026-02-17",
        lookback_days=30,
        market_tz="America/New_York",
    )
    assert Path(out["exec_path"]).exists()


def test_passes_when_lookback_is_within_available_coverage(monkeypatch, tmp_path: Path):
    from core.settings.runtime_config import reset_runtime_config_for_tests

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        f"""
paths:
  marketdata_data_root: {tmp_path}
  trading_artifacts_root: {tmp_path / "artifacts"}
""".strip()
    )
    reset_runtime_config_for_tests()
    monkeypatch.setenv("TRADING_CONFIG", str(cfg))

    _write_derived_m5(
        tmp_path / "derived" / "tf_m5" / "HOOD.parquet",
        start="2026-02-01 14:30:00",
        end="2026-02-10 19:55:00",
    )

    out = ensure_and_snapshot_bars(
        run_dir=tmp_path / "run_ok",
        symbol="HOOD",
        timeframe="M5",
        requested_end="2026-02-10",
        lookback_days=5,
        market_tz="America/New_York",
    )
    assert Path(out["exec_path"]).exists()
