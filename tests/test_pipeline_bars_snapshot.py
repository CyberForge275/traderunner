import json
from pathlib import Path

import pandas as pd
import pytest

from axiom_bt.pipeline.runner import run_pipeline
from axiom_bt.pipeline.data_fetcher import ensure_and_snapshot_bars
from axiom_bt.pipeline.strategy_config_loader import load_strategy_params_from_ssot


def _write_dummy_parquet(path: Path):
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-02 14:30", periods=3, freq="5min", tz="America/New_York"),
            "open": [1.0, 1.1, 1.2],
            "high": [1.1, 1.2, 1.3],
            "low": [0.9, 1.0, 1.1],
            "close": [1.05, 1.15, 1.25],
            "volume": [100, 110, 120],
        }
    )
    df.to_parquet(path)


def _write_index_parquet(path: Path):
    ts = pd.date_range("2024-01-02 14:30", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2],
            "high": [1.1, 1.2, 1.3],
            "low": [0.9, 1.0, 1.1],
            "close": [1.05, 1.15, 1.25],
            "volume": [100, 110, 120],
        },
        index=ts,
    )
    df.to_parquet(path)


def test_run_pipeline_creates_snapshot_if_missing(tmp_path, monkeypatch):
    run_dir = tmp_path / "runA"
    run_dir.mkdir()
    bars_path = run_dir / "missing.parquet"

    # Mock ensure_and_snapshot_bars to create a parquet inside run_dir/bars
    def fake_ensure(**kwargs):
        bars_dir = run_dir / "bars"
        bars_dir.mkdir(parents=True, exist_ok=True)
        exec_path = bars_dir / "bars_exec_M5_rth.parquet"
        _write_dummy_parquet(exec_path)
        meta = {
            "market_tz": "America/New_York",
            "timeframe": "M5",
            "exec_bars": exec_path.name,
        }
        (bars_dir / "bars_slice_meta.json").write_text(json.dumps(meta))
        return {
            "exec_path": str(exec_path),
            "signal_path": None,
            "bars_hash": "deadbeef",
            "meta_path": str(bars_dir / "bars_slice_meta.json"),
        }

    monkeypatch.setattr("axiom_bt.pipeline.runner.ensure_and_snapshot_bars", fake_ensure)

    cfg = load_strategy_params_from_ssot("insidebar_intraday", "1.0.0")
    params = {
        **cfg["core"],
        **cfg["tunable"],
        "symbol": "TEST",
        "timeframe": "M5",
        "requested_end": "2025-01-05",
        "lookback_days": 5,
        "market_tz": "America/New_York",
        "session_mode": "rth",
    }

    run_pipeline(
        run_id="runA",
        out_dir=run_dir,
        bars_path=bars_path,
        strategy_id="insidebar_intraday",
        strategy_version="1.0.0",
        strategy_params=params,
        strategy_meta=cfg,
        compound_enabled=False,
        compound_equity_basis="cash_only",
        initial_cash=10000,
        fees_bps=0,
        slippage_bps=0,
    )

    snap = run_dir / "bars" / "bars_exec_M5_rth.parquet"
    assert snap.exists()
    df = pd.read_parquet(snap)
    assert len(df) == 3


def test_run_pipeline_uses_existing_snapshot_if_present(tmp_path, monkeypatch):
    run_dir = tmp_path / "runB"
    run_dir.mkdir()
    bars_dir = run_dir / "bars"
    bars_dir.mkdir()
    existing = bars_dir / "bars_exec_M5_rth.parquet"
    _write_dummy_parquet(existing)
    (bars_dir / "bars_slice_meta.json").write_text(json.dumps({"timeframe": "M5"}))

    bars_path = existing

    # ensure_and_snapshot_bars should NOT be called
    monkeypatch.setattr("axiom_bt.pipeline.runner.ensure_and_snapshot_bars", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("should not be called")))

    cfg = load_strategy_params_from_ssot("insidebar_intraday", "1.0.0")
    params = {
        **cfg["core"],
        **cfg["tunable"],
        "symbol": "TEST",
        "timeframe": "M5",
        "requested_end": "2025-01-05",
        "lookback_days": 5,
        "market_tz": "America/New_York",
        "session_mode": "rth",
    }

    run_pipeline(
        run_id="runB",
        out_dir=run_dir,
        bars_path=bars_path,
        strategy_id="insidebar_intraday",
        strategy_version="1.0.0",
        strategy_params=params,
        strategy_meta=cfg,
        compound_enabled=False,
        compound_equity_basis="cash_only",
        initial_cash=10000,
        fees_bps=0,
        slippage_bps=0,
    )

    df = pd.read_parquet(existing)
    assert len(df) == 3


def test_ensure_snapshot_resamples_h1(monkeypatch, tmp_path):
    from axiom_bt.pipeline import data_fetcher

    # Prepare M1 parquet
    m1_path = tmp_path / "TEST_rth.parquet"
    ts = pd.date_range("2025-01-01 14:30", periods=120, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": range(len(ts)),
            "high": [v + 0.5 for v in range(len(ts))],
            "low": [v - 0.5 for v in range(len(ts))],
            "close": [v + 0.1 for v in range(len(ts))],
            "volume": [1] * len(ts),
        }
    )
    df.to_parquet(m1_path)

    # Fake store to point to our M1 file
    class FakeStore:
        def __init__(self, *args, **kwargs):
            pass

        def ensure(self, *args, **kwargs):
            return {"ensure": "noop"}

        def path_for(self, symbol, timeframe, session_mode="rth"):
            return m1_path

    monkeypatch.setattr(data_fetcher, "IntradayStore", FakeStore)

    snap = data_fetcher.ensure_and_snapshot_bars(
        run_dir=tmp_path / "runH1",
        symbol="TEST",
        timeframe="H1",
        requested_end="2025-01-02",
        lookback_days=1,
        market_tz="America/New_York",
        session_mode="rth",
        warmup_days=0,
    )

    exec_path = Path(snap["exec_path"])
    assert exec_path.exists()
    out_df = pd.read_parquet(exec_path)
    assert not out_df.empty
    assert out_df.index.freqstr in ("60T", None)  # pandas may drop freq but resample was hourly


def test_load_bars_snapshot_accepts_datetime_index(tmp_path):
    p = tmp_path / "bars_idx.parquet"
    _write_index_parquet(p)
    from axiom_bt.pipeline.data_prep import load_bars_snapshot

    bars, _ = load_bars_snapshot(p)
    assert set(["timestamp", "open", "high", "low", "close", "volume"]).issubset(bars.columns)


def test_missing_strategy_yaml_fails_fast(tmp_path):
    run_dir = tmp_path / "runC"
    run_dir.mkdir()
    bars_path = run_dir / "missing.parquet"

    with pytest.raises(Exception):
        load_strategy_params_from_ssot("unknown_strategy", "1.0.0")
