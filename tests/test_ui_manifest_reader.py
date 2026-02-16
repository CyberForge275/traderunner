import json
from pathlib import Path

from trading_dashboard.services.backtest_ui.manifest_reader import (
    parse_run_result,
    parse_run_steps,
)


def test_parse_run_steps_empty_when_file_missing(tmp_path: Path):
    result = parse_run_steps(tmp_path / "missing.jsonl")
    assert result == []


def test_parse_run_steps_groups_and_final_status(tmp_path: Path):
    steps_file = tmp_path / "run_steps.jsonl"
    steps_file.write_text(
        "\n".join(
            [
                json.dumps({"step_index": 1, "step_name": "fetch_data", "status": "started"}),
                json.dumps({"step_index": 1, "step_name": "fetch_data", "status": "completed"}),
                json.dumps({"step_index": 2, "step_name": "run_model", "status": "started"}),
            ]
        )
    )
    parsed = parse_run_steps(steps_file)
    assert len(parsed) == 2
    assert parsed[0]["step_name"] == "fetch_data"
    assert parsed[0]["final_status"] == "completed"
    assert parsed[0]["icon"] == "✅"
    assert parsed[1]["final_status"] == "running"
    assert parsed[1]["icon"] == "⏳"


def test_parse_run_result_returns_normalized_payload(tmp_path: Path):
    result_file = tmp_path / "run_result.json"
    result_file.write_text(
        json.dumps(
            {
                "status": "error",
                "reason": "boom",
                "error_id": "ERR-123",
                "details": {"signals_count": 10},
            }
        )
    )
    parsed = parse_run_result(result_file)
    assert parsed == {
        "status": "error",
        "reason": "boom",
        "error_id": "ERR-123",
        "details": {"signals_count": 10},
    }


def test_parse_run_result_none_when_missing(tmp_path: Path):
    assert parse_run_result(tmp_path / "missing_result.json") is None
