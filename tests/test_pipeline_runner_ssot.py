import pandas as pd
import pytest
from pathlib import Path

from axiom_bt.pipeline.runner import run_pipeline, PipelineError
from axiom_bt.pipeline.strategy_config_loader import load_strategy_params_from_ssot


def _make_bars(path: Path):
    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=3, freq="5min", tz="UTC"),
        "open": [1, 2, 3],
        "high": [1.1, 2.1, 3.1],
        "low": [0.9, 1.9, 2.9],
        "close": [1.05, 2.05, 3.05],
        "volume": [10, 10, 10],
    })
    df.to_parquet(path)


def test_runner_uses_ssot_market_tz_and_session_mode(monkeypatch, tmp_path):
    run_dir = tmp_path / "run_ssot"
    run_dir.mkdir()
    bars_path = run_dir / "missing.parquet"

    captured = {}

    def fake_ensure(**kwargs):
        captured.update(kwargs)
        bars_dir = run_dir / "bars"
        bars_dir.mkdir(parents=True, exist_ok=True)
        exec_path = bars_dir / "bars_exec_M5_rth.parquet"
        _make_bars(exec_path)
        return {
            "exec_path": str(exec_path),
            "signal_path": None,
            "bars_hash": "abc",
            "meta_path": str(bars_dir / "bars_slice_meta.json"),
        }

    monkeypatch.setattr("axiom_bt.pipeline.runner.ensure_and_snapshot_bars", fake_ensure)

    cfg = load_strategy_params_from_ssot("insidebar_intraday", "1.0.0")
    params = {
        **cfg["core"],
        **cfg["tunable"],
        "symbol": "TEST",
        "timeframe": "M5",
        "requested_end": "2025-01-10",
        "lookback_days": 5,
    }

    run_pipeline(
        run_id="run_ssot",
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

    assert captured["market_tz"] == cfg["core"]["session_timezone"]
    assert captured["session_mode"] == cfg["core"]["session_mode"]


def test_runner_fails_if_session_mode_missing(tmp_path):
    run_dir = tmp_path / "run_missing_session"
    run_dir.mkdir()
    bars_path = run_dir / "bars_exec_M5_rth.parquet"
    _make_bars(bars_path)

    cfg = load_strategy_params_from_ssot("insidebar_intraday", "1.0.0")
    cfg_no_session = {**cfg, "core": {k: v for k, v in cfg["core"].items() if k != "session_mode"}}
    params = {
        **cfg_no_session["core"],
        **cfg_no_session["tunable"],
        "symbol": "TEST",
        "timeframe": "M5",
        "requested_end": "2025-01-10",
        "lookback_days": 5,
    }

    with pytest.raises(PipelineError):
        run_pipeline(
            run_id="run_missing_session",
            out_dir=run_dir,
            bars_path=bars_path,
            strategy_id="insidebar_intraday",
            strategy_version="1.0.0",
            strategy_params=params,
            strategy_meta=cfg_no_session,
            compound_enabled=False,
            compound_equity_basis="cash_only",
            initial_cash=10000,
            fees_bps=0,
            slippage_bps=0,
        )


def test_warmup_days_from_bars(monkeypatch, tmp_path):
    run_dir = tmp_path / "run_warmup"
    run_dir.mkdir()
    bars_path = run_dir / "missing.parquet"

    captured = {}

    def fake_ensure(**kwargs):
        captured.update(kwargs)
        bars_dir = run_dir / "bars"
        bars_dir.mkdir(parents=True, exist_ok=True)
        exec_path = bars_dir / "bars_exec_M5_rth.parquet"
        _make_bars(exec_path)
        return {
            "exec_path": str(exec_path),
            "signal_path": None,
            "bars_hash": "abc",
            "meta_path": str(bars_dir / "bars_slice_meta.json"),
        }

    monkeypatch.setattr("axiom_bt.pipeline.runner.ensure_and_snapshot_bars", fake_ensure)

    cfg = load_strategy_params_from_ssot("insidebar_intraday", "1.0.0")
    cfg_raw = {**cfg, "core": {**cfg["core"], "session_mode": "raw", "timeframe_minutes": 5}}
    cfg_raw["required_warmup_bars"] = 40

    params = {
        **cfg_raw["core"],
        **cfg_raw["tunable"],
        "symbol": "TEST",
        "timeframe": "M5",
        "requested_end": "2025-01-10",
        "lookback_days": 5,
    }

    run_pipeline(
        run_id="run_warmup",
        out_dir=run_dir,
        bars_path=bars_path,
        strategy_id="insidebar_intraday",
        strategy_version="1.0.0",
        strategy_params=params,
        strategy_meta=cfg_raw,
        compound_enabled=False,
        compound_equity_basis="cash_only",
        initial_cash=10000,
        fees_bps=0,
        slippage_bps=0,
    )

    # raw mode: 24h -> 288 bars/day at 5m, warmup_days ceil(40/288)=1
    assert captured.get("warmup_days") == 1


def test_cli_requires_requested_end_and_lookback_days(capsys):
    from axiom_bt.pipeline.cli import main

    with pytest.raises(SystemExit):
        main([
            "--run-id", "demo",
            "--out-dir", "/tmp/demo",
            "--bars-path", "/tmp/demo/bars.csv",
            "--strategy-id", "insidebar_intraday",
            "--strategy-version", "1.0.0",
            "--symbol", "TEST",
            "--timeframe", "M5",
            # missing requested-end and lookback-days
        ])


def test_cli_valid_from_derives_lookback(monkeypatch):
    from axiom_bt.pipeline import cli

    captured = {}

    def fake_run_pipeline(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    cli.main([
        "--run-id", "demo",
        "--out-dir", "/tmp/demo",
        "--bars-path", "/tmp/demo/bars.csv",
        "--strategy-id", "insidebar_intraday",
        "--strategy-version", "1.0.0",
        "--symbol", "TEST",
        "--timeframe", "M5",
        "--valid-from", "2026-01-01",
        "--valid-to", "2026-01-11",
        "--initial-cash", "10000",
    ])

    params = captured.get("strategy_params", {})
    assert params.get("requested_end") == "2026-01-11"
    assert params.get("lookback_days") == 10
