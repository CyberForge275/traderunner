from __future__ import annotations

from pathlib import Path

import pytest

from axiom_bt.pipeline.data_fetcher import (
    MissingHistoricalDataError as PipelineMissingHistoricalDataError,
    ensure_and_snapshot_bars,
)
from axiom_bt.pipeline.runner import PipelineError
from trading_dashboard.services.errors import MissingHistoricalDataError
from trading_dashboard.services.new_pipeline_adapter import NewPipelineAdapter


def test_missing_data_raises_and_never_calls_fetch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "axiom_bt.pipeline.data_fetcher.check_local_m1_coverage",
        lambda **_: {
            "has_gap": True,
            "gaps": [
                {
                    "gap_start": "2025-01-01",
                    "gap_end": "2025-01-31",
                    "gap_days": 31,
                }
            ],
        },
    )

    fetch_called = {"value": False}

    def _no_fetch(*_args, **_kwargs):
        fetch_called["value"] = True
        raise AssertionError("fetch_intraday_1m_to_parquet must not be called")

    monkeypatch.setattr("axiom_bt.intraday.fetch_intraday_1m_to_parquet", _no_fetch)

    with pytest.raises(PipelineMissingHistoricalDataError):
        ensure_and_snapshot_bars(
            run_dir=tmp_path / "run",
            symbol="HYMC",
            timeframe="M5",
            requested_end="2025-05-01",
            lookback_days=30,
            market_tz="America/New_York",
            auto_fill_gaps=False,
        )

    assert fetch_called["value"] is False


def test_dashboard_adapter_raises_domain_missing_data_error(monkeypatch) -> None:
    def _raise_pipeline_missing(*_args, **_kwargs):
        raise PipelineError("failed to ensure bars") from PipelineMissingHistoricalDataError(
            "missing historical bars"
        )

    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.run_pipeline",
        _raise_pipeline_missing,
    )

    adapter = NewPipelineAdapter(progress_callback=lambda _msg: None)

    with pytest.raises(MissingHistoricalDataError) as exc:
        adapter.execute_backtest(
            run_name="run_missing_data",
            strategy="insidebar_intraday",
            symbols=["HYMC"],
            timeframe="M5",
            start_date="2025-01-01",
            end_date="2025-01-31",
            config_params={"strategy_version": "1.0.1"},
        )

    assert "Backfill required" in str(exc.value)
