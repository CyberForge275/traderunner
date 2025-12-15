"""Tests for backtest_log_utils module."""

import json
import pytest
from pathlib import Path
from trading_dashboard.utils.backtest_log_utils import (
    get_pipeline_log_state,
    format_step_icon,
    format_step_color,
    PipelineLogState,
)


@pytest.fixture
def temp_backtests_dir(tmp_path):
    """Create temporary backtests directory."""
    backtests = tmp_path / "backtests"
    backtests.mkdir()
    return backtests


def test_parse_run_log_missing_file(temp_backtests_dir):
    """Test behavior when run_log.json doesn't exist."""
    state = get_pipeline_log_state("nonexistent_run", temp_backtests_dir)
    
    assert state.total_steps == 0
    assert state.completed_steps == 0
    assert state.progress_pct == 0.0
    assert state.overall_status == "pending"
    assert state.current_step is None
    assert len(state.steps) == 0


def test_parse_run_log_success_pipeline(temp_backtests_dir):
    """Test parsing a successful pipeline execution log."""
    run_name = "test_successful_run"
    run_dir = temp_backtests_dir / run_name
    run_dir.mkdir()
    
    # Create mock run_log.json with successful pipeline
    log_data = {
        "status": "success",
        "entries": [
            {"kind": "command", "title": "0) ensure-intraday", "status": "success", "duration": 2.5},
            {"kind": "step", "title": "Data SLA Check", "status": "success", "duration": 0.1},
            {"kind": "command", "title": "1) signals.cli_inside_bar", "status": "success", "duration": 1.2},
            {"kind": "command", "title": "2) trade.cli_export_orders", "status": "success", "duration": 0.5},
            {"kind": "command", "title": "3) axiom_bt.runner", "status": "success", "duration": 5.0},
        ]
    }
    
    log_path = run_dir / "run_log.json"
    log_path.write_text(json.dumps(log_data))
    
    state = get_pipeline_log_state(run_name, temp_backtests_dir)
    
    assert state.total_steps == 5
    assert state.completed_steps == 5
    assert state.progress_pct == 100.0
    assert state.overall_status == "success"
    assert state.current_step is None  # No running step
    assert all(s.status == "success" for s in state.steps)


def test_parse_run_log_with_running_step(temp_backtests_dir):
    """Test parsing a pipeline with currently running step."""
    run_name = "test_running_run"
    run_dir = temp_backtests_dir / run_name
    run_dir.mkdir()
    
    log_data = {
        "status": "running",
        "entries": [
            {"kind": "command", "title": "0) ensure-intraday", "status": "success", "duration": 2.5},
            {"kind": "step", "title": "Data SLA Check", "status": "success", "duration": 0.1},
            {"kind": "command", "title": "1) signals.cli_inside_bar", "status": "running"},
        ]
    }
    
    log_path = run_dir / "run_log.json"
    log_path.write_text(json.dumps(log_data))
    
    state = get_pipeline_log_state(run_name, temp_backtests_dir)
    
    assert state.total_steps == 3
    assert state.completed_steps == 2
    assert state.progress_pct == pytest.approx(66.67, rel=0.1)
    assert state.overall_status == "running"
    assert state.current_step == "1) signals.cli_inside_bar"


def test_parse_run_log_with_error_step(temp_backtests_dir):
    """Test parsing a pipeline with failed step."""
    run_name = "test_failed_run"
    run_dir = temp_backtests_dir / run_name
    run_dir.mkdir()
    
    log_data = {
        "status": "error",
        "entries": [
            {"kind": "command", "title": "0) ensure-intraday", "status": "success", "duration": 2.5},
            {"kind": "step", "title": "Data SLA Check", "status": "warning", "details": "NaN values detected"},
            {"kind": "command", "title": "1) signals.cli_inside_bar", "status": "error", "message": "Failed to process HOOD"},
        ]
    }
    
    log_path = run_dir / "run_log.json"
    log_path.write_text(json.dumps(log_data))
    
    state = get_pipeline_log_state(run_name, temp_backtests_dir)
    
    assert state.total_steps == 3
    assert state.completed_steps == 3  # All have final status
    assert state.progress_pct == 100.0
    assert state.overall_status == "error"
    # Find error step
    error_step = next(s for s in state.steps if s.status == "error")
    assert error_step.name == "1) signals.cli_inside_bar"
    assert "Failed to process HOOD" in error_step.details


def test_parse_run_log_invalid_json(temp_backtests_dir):
    """Test handling of corrupted JSON file."""
    run_name = "test_invalid_json"
    run_dir = temp_backtests_dir / run_name
    run_dir.mkdir()
    
    # Write invalid JSON
    log_path = run_dir / "run_log.json"
    log_path.write_text("{ invalid json }")
    
    state = get_pipeline_log_state(run_name, temp_backtests_dir)
    
    assert state.total_steps == 0
    assert state.overall_status == "error"


def test_format_step_icon():
    """Test step icon formatting."""
    assert format_step_icon("success") == "✅"
    assert format_step_icon("error") == "❌"
    assert format_step_icon("warning") == "⚠️"
    assert format_step_icon("running") == "⏳"
    assert format_step_icon("pending") == "○"
    assert format_step_icon("unknown") == "•"


def test_format_step_color():
    """Test step color formatting."""
    assert format_step_color("success") == "#28a745"
    assert format_step_color("error") == "#dc3545"
    assert format_step_color("warning") == "#ffc107"
    assert format_step_color("running") == "#007bff"
    assert format_step_color("pending") == "#6c757d"


def test_parse_run_log_skips_meta_entries(temp_backtests_dir):
    """Test that run_meta entries are skipped."""
    run_name = "test_meta_skip"
    run_dir = temp_backtests_dir / run_name
    run_dir.mkdir()
    
    log_data = {
        "status": "success",
        "entries": [
            {"kind": "run_meta", "run_name": "test", "strategy": "insidebar"},  # Should be skipped
            {"kind": "command", "title": "0) ensure-intraday", "status": "success"},
            {"kind": "command", "title": "1) signals", "status": "success"},
        ]
    }
    
    log_path = run_dir / "run_log.json"
    log_path.write_text(json.dumps(log_data))
    
    state = get_pipeline_log_state(run_name, temp_backtests_dir)
    
    # Should only have 2 steps (meta entry skipped)
    assert state.total_steps == 2
    assert state.steps[0].name == "0) ensure-intraday"
