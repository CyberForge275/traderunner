import logging

from trading_dashboard.services.backtest_service import BacktestService


class _FakeAdapterRaises:
    def execute_backtest(self, **kwargs):
        raise RuntimeError("synthetic crash")


def test_backtest_service_exception_persists_diagnostics(monkeypatch, tmp_path, caplog):
    import trading_dashboard.services.new_pipeline_adapter as new_pipeline_adapter

    monkeypatch.setenv("TRADING_ARTIFACTS_ROOT", str(tmp_path))
    monkeypatch.setattr(
        new_pipeline_adapter,
        "create_new_adapter",
        lambda progress_callback=None: _FakeAdapterRaises(),
    )

    svc = BacktestService()
    job_id = "job-trace-1"
    run_name = "trace-run-1"
    svc.running_jobs[job_id] = {
        "status": "running",
        "run_name": run_name,
    }

    with caplog.at_level(logging.ERROR):
        svc._run_pipeline(
            job_id=job_id,
            run_name=run_name,
            strategy="insidebar_intraday",
            symbols=["SNDK"],
            timeframe="M5",
            start_date="2026-01-01",
            end_date="2026-01-31",
            config_params={"strategy_version": "1.0.1"},
        )

    assert "actions: backtest_service_pipeline_exception" in caplog.text
    assert job_id in svc.completed_jobs
    job = svc.completed_jobs[job_id]
    assert job["status"] == "failed"
    assert job["error_type"] == "RuntimeError"
    assert "RuntimeError: synthetic crash" in job["error_message"]
    assert job["error_stacktrace_path"]
    with open(job["error_stacktrace_path"], "r", encoding="utf-8") as fh:
        assert "RuntimeError: synthetic crash" in fh.read()
