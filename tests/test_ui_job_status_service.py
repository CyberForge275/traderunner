from datetime import datetime, timezone

from trading_dashboard.services.backtest_ui.job_status_service import (
    collect_jobs_for_polling,
    status_icon_payload,
    status_text,
)


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def test_collect_jobs_for_polling_includes_terminal_statuses():
    jobs = {
        "job-running": {"status": "running"},
        "job-completed": {"status": "completed", "ended_at": _iso_now()},
        "job-failed": {"status": "failed", "ended_at": _iso_now()},
        "job-error": {"status": "error", "ended_at": _iso_now()},
        "job-gate": {"status": "failed_precondition", "ended_at": _iso_now()},
    }

    running, recent = collect_jobs_for_polling(jobs, datetime.now(timezone.utc).timestamp())
    assert "job-running" in running
    assert "job-completed" in recent
    assert "job-failed" in recent
    assert "job-error" in recent
    assert "job-gate" in recent


def test_status_text_mapping():
    assert status_text("completed") == "Completed Successfully"
    assert status_text("failed") == "Failed"
    assert status_text("error") == "Error"
    assert status_text("failed_precondition") == "Failed Precondition (Gates Blocked)"


def test_status_icon_payload_running_priority():
    payload = status_icon_payload({"run1": {"status": "running"}}, {})
    assert payload == {"text": "⏳ Running...", "color": "#888"}


def test_status_icon_payload_terminal_success():
    payload = status_icon_payload({}, {"job1": {"status": "completed"}})
    assert payload == {
        "text": "✅ Complete - Click refresh to update results",
        "color": "green",
    }


def test_status_icon_payload_terminal_failure():
    payload = status_icon_payload({}, {"job1": {"status": "failed"}})
    assert payload == {"text": "⚠️ Failed - Click refresh to see details", "color": "orange"}
