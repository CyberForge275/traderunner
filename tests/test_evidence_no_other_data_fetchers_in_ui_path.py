import pytest

from trading_dashboard.services.new_pipeline_adapter import NewPipelineAdapter
from trading_dashboard.services.errors import MissingHistoricalDataError


def test_no_other_fetchers_used_in_ui_pipeline_path(monkeypatch):
    forbidden = {"count": 0}

    def _boom(*args, **kwargs):
        forbidden["count"] += 1
        raise AssertionError("forbidden fetcher path called")

    # Forbidden legacy producers: must never be used by UI path (Option B consumer-only).
    monkeypatch.setattr("axiom_bt.data.eodhd_fetch.fetch_intraday_1m_to_parquet", _boom)
    monkeypatch.setattr("axiom_bt.intraday.fetch_intraday_1m_to_parquet", _boom)

    import trading_dashboard.data_loading.loaders.eodhd_backfill as eodhd_backfill

    class _BoomBackfill:
        def __init__(self, *args, **kwargs):
            _boom()

    monkeypatch.setattr(eodhd_backfill, "EODHDBackfill", _BoomBackfill)

    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    with pytest.raises(MissingHistoricalDataError):
        adapter.execute_backtest(
            run_name="ev_no_legacy_fetch",
            strategy="insidebar_intraday",
            symbols=["ZZZTEST"],
            timeframe="M5",
            start_date="2026-01-12",
            end_date="2026-02-11",
            config_params={
                "strategy_version": "1.0.1",
                "session_timezone": "America/New_York",
                "session_mode": "rth",
                "session_filter": ["09:30-11:00", "14:00-15:00"],
                "timeframe_minutes": 5,
                "allow_legacy_http_backfill": False,
            },
        )

    assert forbidden["count"] == 0
