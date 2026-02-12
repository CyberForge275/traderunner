from datetime import datetime, timezone

from trading_dashboard.callbacks.run_backtest_callback import (
    _collect_jobs_for_polling,
    _status_text,
)


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def test_collect_jobs_includes_error_and_failed_precondition():
    jobs = {
        "job-running": {"status": "running"},
        "job-completed": {"status": "completed", "ended_at": _iso_now()},
        "job-failed": {"status": "failed", "ended_at": _iso_now()},
        "job-error": {"status": "error", "ended_at": _iso_now()},
        "job-gate": {"status": "failed_precondition", "ended_at": _iso_now()},
    }

    running, recent = _collect_jobs_for_polling(jobs, datetime.now(timezone.utc).timestamp())

    assert "job-running" in running
    assert "job-completed" in recent
    assert "job-failed" in recent
    assert "job-error" in recent
    assert "job-gate" in recent


def test_status_text_covers_terminal_statuses():
    assert _status_text("completed") == "Completed Successfully"
    assert _status_text("failed") == "Failed"
    assert _status_text("error") == "Error"
    assert _status_text("failed_precondition") == "Failed Precondition (Gates Blocked)"
