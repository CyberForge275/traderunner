from __future__ import annotations

from pathlib import Path

import pytest

from axiom_bt.pipeline.data_fetcher import MissingHistoricalDataError, ensure_and_snapshot_bars
from trading_dashboard.data_loading.loaders.eodhd_backfill import EODHDBackfill
from trading_dashboard.services.errors import MissingHistoricalDataError as DashboardMissingHistoricalDataError


def test_intraday_http_fetch_path_blocked_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ALLOW_LEGACY_HTTP_BACKFILL", raising=False)
    monkeypatch.setattr(
        "axiom_bt.pipeline.data_fetcher.check_local_m1_coverage",
        lambda **_: {
            "has_gap": True,
            "gaps": [
                {
                    "gap_start": "2025-01-01",
                    "gap_end": "2025-01-10",
                    "gap_days": 10,
                    "reason": "before_existing_data",
                }
            ],
        },
    )

    def _fail_http_fetch(*_args, **_kwargs):
        raise AssertionError("HTTP fetch must not be called when legacy backfill is disabled")

    def _fail_store_ensure(*_args, **_kwargs):
        raise AssertionError("IntradayStore.ensure must not be called when gaps are blocked")

    monkeypatch.setattr("axiom_bt.intraday.fetch_intraday_1m_to_parquet", _fail_http_fetch)
    monkeypatch.setattr("axiom_bt.pipeline.data_fetcher.IntradayStore.ensure", _fail_store_ensure)

    with pytest.raises(MissingHistoricalDataError) as exc:
        ensure_and_snapshot_bars(
            run_dir=tmp_path / "run",
            symbol="WDC",
            timeframe="M5",
            requested_end="2026-02-11",
            lookback_days=300,
            market_tz="America/New_York",
            auto_fill_gaps=True,
            allow_legacy_http_backfill=False,
        )
    assert "marketdata_service.backfill_cli" in str(exc.value)


def test_dashboard_eodhd_backfill_loader_disabled() -> None:
    with pytest.raises(DashboardMissingHistoricalDataError) as exc:
        EODHDBackfill(api_key="dummy")
    assert "marketdata_service.backfill_cli" in str(exc.value)
