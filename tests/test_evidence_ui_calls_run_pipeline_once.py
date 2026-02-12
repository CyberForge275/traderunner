from trading_dashboard.services.new_pipeline_adapter import NewPipelineAdapter


def test_ui_adapter_calls_run_pipeline_once(monkeypatch):
    calls = {"count": 0}

    def _fake_run_pipeline(**kwargs):
        calls["count"] += 1
        raise RuntimeError("stop_after_entry")

    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.run_pipeline",
        _fake_run_pipeline,
    )

    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    result = adapter.execute_backtest(
        run_name="ev_ui_once",
        strategy="insidebar_intraday",
        symbols=["WDC"],
        timeframe="M5",
        start_date="2026-01-12",
        end_date="2026-02-11",
        config_params={
            "strategy_version": "1.0.1",
            "session_timezone": "America/New_York",
            "session_mode": "rth",
            "session_filter": ["09:30-11:00", "14:00-15:00"],
            "timeframe_minutes": 5,
        },
    )

    assert calls["count"] == 1
    assert result["status"] == "failed"
    assert "stop_after_entry" in result.get("error", "")
