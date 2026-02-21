import json
import pandas as pd
import pytest
from pathlib import Path
from types import SimpleNamespace

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


def test_cli_uses_yaml_for_cost_defaults_when_not_passed(monkeypatch):
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
        "--requested-end", "2026-01-11",
        "--lookback-days", "10",
    ])

    base_cfg = captured.get("base_config_path")
    assert base_cfg is not None
    assert str(base_cfg).endswith("configs/runs/backtest_pipeline_defaults.yaml")
    cli_costs = captured["config_overrides"]["cli"].get("costs", {})
    assert "commission_bps" not in cli_costs
    assert "slippage_bps" not in cli_costs


def test_pipeline_runner_has_default_base_config_yaml():
    from axiom_bt.pipeline.runner import _default_base_config_path

    path = _default_base_config_path()
    assert path is not None
    assert str(path).endswith("configs/runs/backtest_pipeline_defaults.yaml")


def test_runner_single_generate_fills_call_with_probe_enabled(monkeypatch, tmp_path):
    run_dir = tmp_path / "run_probe_single_call"
    run_dir.mkdir()
    bars_path = run_dir / "bars_exec_M15_rth.parquet"
    bars_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01 14:30:00+00:00", periods=4, freq="15min", tz="UTC"),
            "open": [100.0, 100.2, 100.1, 100.3],
            "high": [100.5, 100.7, 100.6, 100.8],
            "low": [99.8, 99.9, 99.7, 99.9],
            "close": [100.2, 100.1, 100.3, 100.4],
            "volume": [1, 1, 1, 1],
        }
    )
    bars_df.to_parquet(bars_path)

    base_cfg = tmp_path / "base.yaml"
    base_cfg.write_text(
        """
costs:
  commission_bps: 2.0
  slippage_bps: 1.0
execution:
  allow_same_bar_exit: true
  same_bar_resolution_mode: m1_probe_then_no_fill
  intrabar_probe_timeframe: M1
""".strip()
    )

    monkeypatch.setattr(
        "axiom_bt.pipeline.runner.build_signal_frame",
        lambda **kwargs: (
            pd.DataFrame({"signal_ts": [pd.Timestamp("2025-01-01 14:30:00+00:00")]}),
            [{"name": "signal_ts", "dtype": "datetime64[ns, UTC]"}],
        ),
    )
    monkeypatch.setattr(
        "axiom_bt.pipeline.runner.compute_schema_fingerprint",
        lambda schema: {
            "schema_version": "1.0.0",
            "schema_hash": "abc",
            "column_count": 1,
        },
    )

    class _FakeAdapter:
        def generate_intent(self, *_args, **_kwargs):
            events_intent = pd.DataFrame(
                [
                    {
                        "template_id": "t1",
                        "signal_ts": pd.Timestamp("2025-01-01 14:30:00+00:00"),
                        "symbol": "TEST",
                        "side": "BUY",
                        "entry_price": 100.0,
                        "stop_price": 99.5,
                        "take_profit_price": 100.8,
                        "order_valid_to_ts": pd.Timestamp("2025-01-01 14:45:00+00:00"),
                    }
                ]
            )
            return SimpleNamespace(
                events_intent=events_intent,
                intent_hash="intent_hash",
                signals_frame=events_intent.copy(),
            )

    monkeypatch.setattr("axiom_bt.pipeline.runner.get_strategy_adapter", lambda _sid: _FakeAdapter())
    monkeypatch.setattr(
        "axiom_bt.pipeline.runner._load_intrabar_probe_bars_m1",
        lambda **kwargs: pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01 14:30:00+00:00", periods=2, freq="1min", tz="UTC"),
                "open": [100.0, 100.1],
                "high": [100.2, 100.3],
                "low": [99.9, 100.0],
                "close": [100.1, 100.2],
            }
        ),
    )

    calls = {"count": 0}

    def _fake_generate_fills(*args, **kwargs):
        calls["count"] += 1
        raise RuntimeError("stop_after_generate_fills")

    monkeypatch.setattr("axiom_bt.pipeline.runner.generate_fills", _fake_generate_fills)

    with pytest.raises(RuntimeError, match="stop_after_generate_fills"):
        run_pipeline(
            run_id="run_probe_single_call",
            out_dir=run_dir,
            bars_path=bars_path,
            strategy_id="insidebar_intraday",
            strategy_version="1.0.3",
            strategy_params={
                "symbol": "TEST",
                "timeframe": "M15",
                "requested_end": "2025-01-03",
                "lookback_days": 3,
                "session_timezone": "America/New_York",
                "session_mode": "rth",
                "session_filter": ["09:30-11:00", "14:00-15:00"],
                "order_validity_policy": "session_end",
            },
            strategy_meta={
                "core": {
                    "timeframe_minutes": 15,
                    "session_timezone": "America/New_York",
                    "session_mode": "rth",
                },
                "tunable": {},
                "required_warmup_bars": 0,
            },
            compound_enabled=False,
            compound_equity_basis="cash_only",
            initial_cash=10000,
            fees_bps=2.0,
            slippage_bps=1.0,
            base_config_path=base_cfg,
            config_overrides={},
        )

    assert calls["count"] == 1


def test_runner_writes_run_steps_when_enabled(monkeypatch, tmp_path):
    run_dir = tmp_path / "run_steps_enabled"
    run_dir.mkdir()
    bars_path = run_dir / "bars_exec_M5_rth.parquet"
    _make_bars(bars_path)

    cfg_file = tmp_path / "trading.yaml"
    cfg_file.write_text(
        """
paths:
  marketdata_data_root: /var/lib/trading/marketdata
  trading_artifacts_root: /var/lib/trading/artifacts
runtime:
  pipeline_write_run_steps: true
""".strip()
    )
    monkeypatch.setenv("TRADING_CONFIG", str(cfg_file))
    from core.settings.runtime_config import reset_runtime_config_for_tests
    reset_runtime_config_for_tests()

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
        run_id="run_steps_enabled",
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

    steps_file = run_dir / "run_steps.jsonl"
    assert steps_file.exists()
    lines = [line.strip() for line in steps_file.read_text().splitlines() if line.strip()]
    assert lines

    first_event = json.loads(lines[0])
    assert first_event["status"] == "started"
    assert first_event["step_name"] == "load_or_fetch_bars"


def test_runner_does_not_write_run_steps_when_disabled(monkeypatch, tmp_path):
    run_dir = tmp_path / "run_steps_disabled"
    run_dir.mkdir()
    bars_path = run_dir / "bars_exec_M5_rth.parquet"
    _make_bars(bars_path)

    cfg_file = tmp_path / "trading.yaml"
    cfg_file.write_text(
        """
paths:
  marketdata_data_root: /var/lib/trading/marketdata
  trading_artifacts_root: /var/lib/trading/artifacts
runtime:
  pipeline_write_run_steps: false
""".strip()
    )
    monkeypatch.setenv("TRADING_CONFIG", str(cfg_file))
    from core.settings.runtime_config import reset_runtime_config_for_tests
    reset_runtime_config_for_tests()

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
        run_id="run_steps_disabled",
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

    assert not (run_dir / "run_steps.jsonl").exists()
