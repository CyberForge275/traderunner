from __future__ import annotations

from trading_dashboard.services.new_pipeline_adapter import NewPipelineAdapter


def test_execute_backtest_uses_runtime_config_consumer_only_when_env_missing(monkeypatch, tmp_path):
    captured = {}

    cfg = tmp_path / "trading.yaml"
    cfg.write_text(
        """
paths:
  marketdata_data_root: /var/lib/trading/marketdata
  trading_artifacts_root: /var/lib/trading/artifacts
runtime:
  pipeline_consumer_only: true
""".strip()
    )

    def _fake_run_pipeline(**kwargs):
        captured.update(kwargs)
        raise RuntimeError("stop_after_capture")

    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.run_pipeline",
        _fake_run_pipeline,
    )
    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.MarketdataStreamClient.is_configured",
        lambda self: False,
    )
    monkeypatch.setenv("TRADING_CONFIG", str(cfg))
    monkeypatch.delenv("PIPELINE_CONSUMER_ONLY", raising=False)
    monkeypatch.delenv("MARKETDATA_STREAM_URL", raising=False)

    from core.settings.runtime_config import reset_runtime_config_for_tests

    reset_runtime_config_for_tests()
    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    result = adapter.execute_backtest(
        run_name="runtime_consumer_only",
        strategy="insidebar_intraday",
        symbols=["SOUN"],
        timeframe="M5",
        start_date="2026-02-10",
        end_date="2026-02-11",
        config_params={
            "strategy_version": "1.0.1",
            "lookback_days": 30,
            "session_timezone": "America/New_York",
            "session_mode": "rth",
            "session_filter": ["09:30-11:00", "14:00-15:00"],
            "timeframe_minutes": 5,
        },
    )

    assert result["status"] == "failed"
    assert "stop_after_capture" in result.get("error", "")
    assert captured["strategy_params"]["consumer_only"] is True


def test_execute_backtest_defers_stream_url_resolution_to_client(monkeypatch):
    captured = {"base_urls": []}

    class _ClientStub:
        def __init__(self, base_url=None, timeout_sec=None, enabled=None):
            captured["base_urls"].append(base_url)
            self.base_url = "stub"

        def is_configured(self):
            return False

    def _fake_run_pipeline(**kwargs):
        raise RuntimeError("stop_after_capture")

    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.run_pipeline",
        _fake_run_pipeline,
    )
    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.MarketdataStreamClient",
        _ClientStub,
    )
    monkeypatch.setenv("MARKETDATA_STREAM_URL", "http://env-url:8090")

    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    result = adapter.execute_backtest(
        run_name="runtime_stream_url",
        strategy="insidebar_intraday",
        symbols=["SOUN"],
        timeframe="M5",
        start_date="2026-02-10",
        end_date="2026-02-11",
        config_params={
            "strategy_version": "1.0.1",
            "lookback_days": 30,
            "session_timezone": "America/New_York",
            "session_mode": "rth",
            "session_filter": ["09:30-11:00", "14:00-15:00"],
            "timeframe_minutes": 5,
        },
    )

    assert result["status"] == "failed"
    assert captured["base_urls"][0] is None
