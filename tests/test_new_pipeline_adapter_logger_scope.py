from trading_dashboard.services.new_pipeline_adapter import NewPipelineAdapter


def test_execute_backtest_no_unboundlocalerror_on_logger(monkeypatch):
    import trading_dashboard.services.new_pipeline_adapter as mod

    def _stop_pipeline(**kwargs):
        raise RuntimeError("stop")

    monkeypatch.setattr(mod, "run_pipeline", _stop_pipeline)

    adapter = NewPipelineAdapter(progress_callback=lambda msg: None)
    result = adapter.execute_backtest(
        run_name="test_run",
        strategy="insidebar_intraday",
        symbols=["HOOD"],
        timeframe="M5",
        start_date="2026-01-01",
        end_date="2026-01-02",
        config_params={"strategy_version": "1.0.1"},
    )

    assert result["status"] == "failed"
    assert "UnboundLocalError" not in result.get("error", "")
    assert "RuntimeError" in result.get("traceback", "")
