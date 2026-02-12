from trading_dashboard.services.new_pipeline_adapter import NewPipelineAdapter


def test_execute_backtest_passes_ui_lookback_days_to_pipeline(monkeypatch):
    captured = {}

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

    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    result = adapter.execute_backtest(
        run_name="lookback_passthrough",
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
    assert captured["strategy_params"]["lookback_days"] == 30
    assert captured["strategy_params"]["lookback_days"] != 1
