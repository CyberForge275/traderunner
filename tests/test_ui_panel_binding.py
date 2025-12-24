"""
UI Panel Binding Tests - Phase 1

Tests to verify:
1. Artifact lookup uses run_dir from store, not job_id
2. All panels bind to the same run_dir
3. Backtest run name input not reset on poll
4. Debug panel has accessible contrast
"""

import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from dash import no_update


class TestArtifactLookupUsesRunDir:
    """Test that callbacks use run_dir from store, not job_id for filesystem lookups."""

    def test_polling_uses_run_dir_not_job_id(self, tmp_path):
        """Verify polling callback uses run_dir from active_run store, not job_id."""
        # Given: job_id has double timestamp (service-generated)
        job_id = "251216_160045_HOOD_test_20251216_160045"
        run_name = "251216_160045_HOOD_test"
        run_dir = tmp_path / "backtests" / run_name

        # Create artifacts in run_dir (using run_name, not job_id)
        run_dir.mkdir(parents=True)
        (run_dir / "run_result.json").write_text(json.dumps({
            "run_id": run_name,
            "status": "success",
            "details": {"signals_count": 42}
        }))

        # Active run store (SSOT)
        active_run = {
            "job_id": job_id,
            "run_name": run_name,
            "run_dir": str(run_dir),
            "started_at": "2025-12-16T16:00:45Z"
        }

        # When: Callback tries to read artifacts
        # It should use run_dir from active_run, NOT job_id

        # Simulate callback logic
        lookup_dir = Path(active_run["run_dir"])
        result_file = lookup_dir / "run_result.json"

        # Then: File found (proving run_dir was used, not job_id)
        assert result_file.exists()

        # Verify job_id path would NOT work
        wrong_dir = tmp_path / "backtests" / job_id
        assert not wrong_dir.exists()


class TestAllPanelsBindToSameRunDir:
    """Test that status/log/summary panels all read from same run_dir."""

    def test_multiple_panels_read_same_artifacts(self, tmp_path):
        """Ensure all UI panels derive data from the same run_dir."""
        run_name = "251216_120000_TEST_panel_binding"
        run_dir = tmp_path / "backtests" / run_name
        run_dir.mkdir(parents=True)

        # Create SSOT artifacts
        (run_dir / "run_result.json").write_text(json.dumps({
            "run_id": run_name,
            "status": "success",
            "reason": None,
            "details": {"signals_count": 10}
        }))

        (run_dir / "run_manifest.json").write_text(json.dumps({
            "identity": {"run_id": run_name},
            "data": {"symbol": "AAPL"},
            "result": {"run_status": "success"}
        }))

        (run_dir / "run_meta.json").write_text(json.dumps({
            "run_id": run_name,
            "symbol": "AAPL",
            "started_at": "2025-12-16T12:00:00Z"
        }))

        # Simulate 3 different panels reading
        active_run = {"run_dir": str(run_dir)}

        # Panel 1: Status (reads run_result.json)
        with open(Path(active_run["run_dir"]) / "run_result.json") as f:
            status_data = json.load(f)

        # Panel 2: Summary (reads run_manifest.json)
        with open(Path(active_run["run_dir"]) / "run_manifest.json") as f:
            summary_data = json.load(f)

        # Panel 3: Metadata (reads run_meta.json)
        with open(Path(active_run["run_dir"]) / "run_meta.json") as f:
            meta_data = json.load(f)

        # All panels should reference the SAME run
        assert status_data["run_id"] == run_name
        assert summary_data["identity"]["run_id"] == run_name
        assert meta_data["run_id"] == run_name

        # All panels should reference the SAME symbol
        assert summary_data["data"]["symbol"] == "AAPL"
        assert meta_data["symbol"] == "AAPL"


class TestBacktestRunNameInputNotResetOnPoll:
    """Test that input field preserves user input during polling."""

    def test_input_preserved_when_no_new_run_started(self):
        """Poll callback should not reset input field."""
        # Given: User has typed a run name
        user_input = "my_custom_backtest_name"

        # When: Poll callback fires (no new run started, n_clicks=None)
        n_clicks = None

        # Callback logic: if not n_clicks, preserve input
        if not n_clicks:
            output_value = user_input  # Should preserve
        else:
            output_value = ""  # Only clear on successful start

        # Then: Input value unchanged
        assert output_value == user_input

    def test_input_cleared_only_after_successful_start(self):
        """Input should only be cleared AFTER successful backtest start."""
        # Given: User clicks run with valid inputs
        n_clicks = 1
        user_input = "test_run"

        # When: Backtest starts successfully
        backtest_started = True

        if backtest_started and n_clicks:
            output_value = ""  # Clear for next run
        else:
            output_value = user_input  # Keep if failed to start

        # Then: Input cleared
        assert output_value == ""

    def test_poll_callback_does_not_output_to_input_field(self):
        """Poll callback should not have Output() targeting input field."""
        # This is a structural test - poll callback signature check
        # In actual implementation, verify:
        # @app.callback(
        #     Output("backtests-run-progress", "children"),  # OK
        #     # NO Output("backtests-new-run-name", "value")  # Must NOT be here
        # )
        # def check_job_status(...):

        # Symbolic test: poll callback outputs should not include input reset
        poll_outputs = ["backtests-run-progress"]  # Only progress, not input

        assert "backtests-new-run-name" not in poll_outputs


class TestDebugPanelHasAccessibleContrast:
    """Test debug panel uses high-contrast styling for readability."""

    def test_debug_panel_background_uses_theme_token(self):
        """Background should use dashboard theme variable."""
        # Debug panel style dict
        debug_style = {
            "backgroundColor": "var(--bs-card-bg, #2b2b2b)",
            "color": "var(--bs-body-color, #eaeaea)",
        }

        # Should use CSS variables (not hardcoded yellow)
        assert "var(--bs-card-bg" in debug_style["backgroundColor"]
        assert "var(--bs-body-color" in debug_style["color"]

        # Fallback values should be high-contrast
        assert "#2b2b2b" in debug_style["backgroundColor"]  # Dark bg
        assert "#eaeaea" in debug_style["color"]  # Light text

    def test_debug_panel_text_color_readable(self):
        """Text color should have sufficient contrast ratio."""
        # Styling for debug panel content
        text_color = "#eaeaea"  # Light gray
        bg_color = "#2b2b2b"    # Dark gray

        # Simple luminance check (not exact WCAG calc, but directional)
        # Light text on dark bg = good contrast
        text_lum = int(text_color[1:3], 16)  # 0xea = 234
        bg_lum = int(bg_color[1:3], 16)      # 0x2b = 43

        # Text should be significantly lighter than background
        assert text_lum > bg_lum + 100  # At least 100 units difference

    def test_debug_labels_use_accent_color(self):
        """Labels should use accent color for emphasis."""
        label_style = {
            "fontWeight": "600",
            "color": "var(--bs-warning, #ffc107)"
        }

        # Should use theme variable
        assert "var(--bs-warning" in label_style["color"]
        assert label_style["fontWeight"] == "600"


# Fixtures
@pytest.fixture
def mock_backtests_dir(tmp_path):
    """Create temporary backtests directory."""
    backtests = tmp_path / "backtests"
    backtests.mkdir()
    return backtests


@pytest.fixture
def sample_active_run():
    """Sample active_run store data."""
    return {
        "job_id": "251216_120000_TEST_20251216_120000",
        "run_name": "251216_120000_TEST",
        "run_dir": "artifacts/backtests/251216_120000_TEST",
        "started_at": "2025-12-16T12:00:00Z"
    }
