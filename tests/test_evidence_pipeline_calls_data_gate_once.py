from pathlib import Path

import pytest

from axiom_bt.pipeline.runner import run_pipeline


def test_pipeline_calls_data_gate_once(monkeypatch, tmp_path):
    calls = {"count": 0}

    def _fake_ensure_and_snapshot_bars(**kwargs):
        calls["count"] += 1
        raise RuntimeError("stop_after_data_gate")

    monkeypatch.setattr(
        "axiom_bt.pipeline.runner.ensure_and_snapshot_bars",
        _fake_ensure_and_snapshot_bars,
    )

    run_dir = tmp_path / "ev_run"
    bars_path = run_dir / "bars_snapshot.parquet"

    with pytest.raises(RuntimeError, match="stop_after_data_gate"):
        run_pipeline(
            run_id="ev_run",
            out_dir=run_dir,
            bars_path=bars_path,
            strategy_id="insidebar_intraday",
            strategy_version="1.0.1",
            strategy_params={
                "symbol": "WDC",
                "timeframe": "M5",
                "requested_end": "2026-02-11",
                "lookback_days": 30,
                "consumer_only": True,
            },
            strategy_meta={
                "core": {
                    "timeframe_minutes": 5,
                    "session_timezone": "America/New_York",
                    "session_mode": "rth",
                },
                "tunable": {},
                "required_warmup_bars": 0,
            },
            compound_enabled=True,
            compound_equity_basis="cash_only",
            initial_cash=10000.0,
            fees_bps=2.0,
            slippage_bps=1.0,
        )

    assert calls["count"] == 1
