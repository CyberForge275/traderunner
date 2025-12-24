"""
Tests for Manifest Writer

Verifies manifest creation for all run outcomes.
"""

import pytest
import json
from pathlib import Path

from backtest.services.manifest_writer import ManifestWriter
from backtest.services.run_status import RunResult, RunStatus, FailureReason


class TestManifestWriter:
    """Test manifest writer for all outcomes."""

    def test_manifest_exists_on_success(self, tmp_path):
        """Verify run_manifest.json exists on SUCCESS."""
        run_dir = tmp_path / "test_success"
        run_dir.mkdir()

        writer = ManifestWriter(run_dir)

        # Write initial manifest
        writer.write_initial_manifest(
            run_id="test_success",
            strategy_key="inside_bar",
            impl_version="1.0.0",
            profile_version="default",
            params={"atr_period": 14},
            symbol="HOOD",
            requested_tf="M15",
            base_tf="M5",
            lookback_days=100,
            requested_end="2025-12-12"
        )

        # Finalize with SUCCESS
        result = RunResult(
            run_id="test_success",
            status=RunStatus.SUCCESS,
            details={"signals": 42}
        )

        writer.finalize_manifest(result, artifacts_produced=["signals.json", "trades.json"])

        # Verify manifest exists
        manifest_path = run_dir / "run_manifest.json"
        assert manifest_path.exists()

        # Verify content
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["identity"]["run_id"] == "test_success"
        assert manifest["identity"]["market_tz"] == "America/New_York"
        assert manifest["strategy"]["key"] == "inside_bar"
        assert manifest["strategy"]["impl_version"] == "1.0.0"
        assert manifest["result"]["run_status"] == "success"
        assert "signals.json" in manifest["result"]["artifacts_index"]

    def test_manifest_exists_on_failed_precondition(self, tmp_path):
        """Verify run_manifest.json exists on FAILED_PRECONDITION."""
        run_dir = tmp_path / "test_failed_precond"
        run_dir.mkdir()

        writer = ManifestWriter(run_dir)

        writer.write_initial_manifest(
            run_id="test_failed_precond",
            strategy_key="inside_bar",
            impl_version="1.0.0",
            profile_version="default",
            params={},
            symbol="HOOD",
            requested_tf="M15",
            base_tf="M15",
            lookback_days=100,
            requested_end="2025-12-12"
        )

        # Finalize with FAILED_PRECONDITION
        result = RunResult(
            run_id="test_failed_precond",
            status=RunStatus.FAILED_PRECONDITION,
            reason=FailureReason.DATA_COVERAGE_GAP,
            details={"gap": {"start": "2025-12-05", "end": "2025-12-12"}}
        )

        writer.finalize_manifest(result)

        # Verify manifest exists
        manifest_path = run_dir / "run_manifest.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["result"]["run_status"] == "failed_precondition"
        assert manifest["result"]["failure_reason"] == "data_coverage_gap"
        assert "gap" in manifest["result"]["failure_details"]

    def test_manifest_exists_on_error(self, tmp_path):
        """Verify run_manifest.json exists on ERROR with error_id."""
        run_dir = tmp_path / "test_error"
        run_dir.mkdir()

        writer = ManifestWriter(run_dir)

        writer.write_initial_manifest(
            run_id="test_error",
            strategy_key="inside_bar",
            impl_version="1.0.0",
            profile_version="default",
            params={},
            symbol="HOOD",
            requested_tf="M15",
            base_tf="M15",
            lookback_days=100,
            requested_end="2025-12-12"
        )

        # Finalize with ERROR
        error_id = "ABC123DEF456"
        result = RunResult(
            run_id="test_error",
            status=RunStatus.ERROR,
            error_id=error_id,
            details={"exception": "UnhandledError"}
        )

        writer.finalize_manifest(result)

        # Verify manifest exists
        manifest_path = run_dir / "run_manifest.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["result"]["run_status"] == "error"
        assert manifest["result"]["error_id"] == error_id
        assert manifest["result"]["failure_reason"] is None  # ERROR has no FailureReason

    def test_manifest_contains_required_keys(self, tmp_path):
        """Verify manifest contains all required keys."""
        run_dir = tmp_path / "test_schema"
        run_dir.mkdir()

        writer = ManifestWriter(run_dir)

        writer.write_initial_manifest(
            run_id="test_schema",
            strategy_key="inside_bar",
            impl_version="1.0.0",
            profile_version="default",
            params={"atr_period": 14},
            symbol="HOOD",
            requested_tf="M15",
            base_tf="M5",
            lookback_days=100,
            requested_end="2025-12-12"
        )

        manifest_path = run_dir / "run_manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        # Verify top-level keys
        assert "identity" in manifest
        assert "strategy" in manifest
        assert "params" in manifest
        assert "data" in manifest
        assert "gates" in manifest
        assert "result" in manifest

        # Verify identity keys
        assert "run_id" in manifest["identity"]
        assert "timestamp_utc" in manifest["identity"]
        assert "market_tz" in manifest["identity"]

        # Verify strategy keys
        assert "key" in manifest["strategy"]
        assert "impl_version" in manifest["strategy"]
        assert "profile_version" in manifest["strategy"]

        # Verify data keys
        assert "symbol" in manifest["data"]
        assert "requested_tf" in manifest["data"]
        assert "base_tf_used" in manifest["data"]
        assert "requested_range" in manifest["data"]

    def test_market_tz_always_america_new_york(self, tmp_path):
        """Verify market_tz is always America/New_York (immutable)."""
        run_dir = tmp_path / "test_tz"
        run_dir.mkdir()

        writer = ManifestWriter(run_dir)

        writer.write_initial_manifest(
            run_id="test_tz",
            strategy_key="inside_bar",
            impl_version="1.0.0",
            profile_version="default",
            params={},
            symbol="HOOD",
            requested_tf="M15",
            base_tf="M15",
            lookback_days=100,
            requested_end="2025-12-12"
        )

        manifest_path = run_dir / "run_manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["identity"]["market_tz"] == "America/New_York"

    def test_base_tf_used_recorded_correctly(self, tmp_path):
        """Verify base_tf_used is recorded in manifest."""
        run_dir = tmp_path / "test_base_tf"
        run_dir.mkdir()

        writer = ManifestWriter(run_dir)

        # Test M5 as base TF
        writer.write_initial_manifest(
            run_id="test_base_tf",
            strategy_key="inside_bar",
            impl_version="1.0.0",
            profile_version="default",
            params={},
            symbol="HOOD",
            requested_tf="M15",
            base_tf="M5",  # M5 is base
            lookback_days=100,
            requested_end="2025-12-12"
        )

        manifest_path = run_dir / "run_manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["data"]["base_tf_used"] == "M5"
        assert manifest["data"]["requested_tf"] == "M15"


class TestManifestIntegration:
    """Test manifest integration with artifacts manager."""

    def test_artifacts_manager_creates_manifest(self, tmp_path):
        """Verify artifacts manager creates manifest via manifest writer."""
        from backtest.services.artifacts_manager import ArtifactsManager

        manager = ArtifactsManager(artifacts_root=tmp_path)

        run_id = "test_integration"
        manager.create_run_dir(run_id)

        manager.write_run_meta(
            strategy="inside_bar",
            symbols=["HOOD"],
            timeframe="M15",
            params={"atr_period": 14},
            requested_end="2025-12-12",
            lookback_days=100,
            impl_version="1.0.0",
            profile_version="default"
        )

        # Verify manifest was created
        manifest_path = tmp_path / run_id / "run_manifest.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["identity"]["run_id"] == run_id
        assert manifest["strategy"]["impl_version"] == "1.0.0"

    def test_manifest_finalized_with_run_result(self, tmp_path):
        """Verify manifest is finalized when run_result is written."""
        from backtest.services.artifacts_manager import ArtifactsManager

        manager = ArtifactsManager(artifacts_root=tmp_path)

        run_id = "test_finalize"
        manager.create_run_dir(run_id)

        manager.write_run_meta(
            strategy="inside_bar",
            symbols=["HOOD"],
            timeframe="M15",
            params={},
            requested_end="2025-12-12",
            lookback_days=100
        )

        # Write run result
        result = RunResult(
            run_id=run_id,
            status=RunStatus.SUCCESS,
            details={}
        )

        manager.write_run_result(result, artifacts_produced=["signals.json"])

        # Verify manifest was finalized
        manifest_path = tmp_path / run_id / "run_manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["result"]["run_status"] == "success"
        assert "signals.json" in manifest["result"]["artifacts_index"]
