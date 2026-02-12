from trading_dashboard.services.backtest_service import BacktestService


class _FakeAdapterFailed:
    def execute_backtest(self, **kwargs):
        return {
            "status": "failed",
            "error": "synthetic adapter failure",
            "traceback": "traceback-lines",
            "run_name": kwargs["run_name"],
            "run_dir": "/tmp/fake_run",
        }


def test_adapter_failed_status_stays_failed(monkeypatch):
    import trading_dashboard.services.new_pipeline_adapter as new_pipeline_adapter

    monkeypatch.setattr(new_pipeline_adapter, "create_new_adapter", lambda progress_callback=None: _FakeAdapterFailed())

    svc = BacktestService()
    job_id = "job-1"
    svc.running_jobs[job_id] = {
        "status": "running",
        "run_name": "run-a",
    }

    svc._run_pipeline(
        job_id=job_id,
        run_name="run-a",
        strategy="insidebar_intraday",
        symbols=["WDC"],
        timeframe="M5",
        start_date="2026-01-01",
        end_date="2026-01-31",
        config_params={"strategy_version": "1.0.1"},
    )

    assert job_id in svc.completed_jobs
    job = svc.completed_jobs[job_id]
    assert job["status"] == "failed"
    assert "synthetic adapter failure" in job.get("error", "")
    assert "traceback-lines" in job.get("traceback", "")
    assert job["run_name"] == "run-a"
