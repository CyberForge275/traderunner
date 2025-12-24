"""
Golden Backtest Atom Test

CRITICAL: This test defines the Golden Atom - stable, known-good configuration.

Golden Atom = APP M5 with fixed strategy versions.

RULES:
1. If this test FAILS after code change → MUST bump impl/profile version
2. Assertions use tolerances/counts (not brittle file hashes)
3. This test guards SSOT stability for Pre-Paper promotion

Golden Config:
- Symbol: APP (known stable data, good liquidity)
- Base TF: M5 (stable SSOT)
- Strategy: inside_bar v1.0.0 / profile:default
- Lookback: 100 days (sufficient history)
"""

import pytest
import json
import os
from pathlib import Path

from backtest.examples.minimal_pipeline import minimal_backtest_with_gates
from backtest.services.run_status import RunStatus, FailureReason


class TestGoldenBacktestAtom:
    """
    Golden Atom Test - SSOT Stability Gate.
    
    This test MUST pass for approved atoms.
    Failure after code change requires version bump.
    """
    
    @pytest.mark.golden
    def test_golden_atom_app_m5_inside_bar(self, tmp_path):
        """
        GOLDEN ATOM TEST
        
        Symbol: APP
        Base TF: M5
        Strategy: inside_bar v1.0.0 / default
        Lookback: 100 days
        
        Expected: SUCCESS with deterministic metrics within tolerances.
        
        If this fails after code change:
        1. Verify if behavior change is intentional
        2. If intentional: BUMP impl_version or profile_version
        3. Update this test's expected ranges
        4. Document change in BACKTEST_ATOM.md
        """
        # Run golden atom
        result = minimal_backtest_with_gates(
            run_id="golden_atom_app_m5",
            symbol="APP",
            timeframe="M5",
            requested_end="2025-12-15",  # Recent date
            lookback_days=100,
            strategy_params={
                "atr_period": 14,
                "min_mother_bar_size_atr_multiple": 1.5,
                "require_close_beyond_mother": True,
                "risk_reward_ratio": 2.0,
                "lookback_candles": 50,
                "max_pattern_age_candles": 5
            },
            artifacts_root=tmp_path
        )
        
        # CRITICAL: Golden Atom MUST succeed (when data available)
        if result.status == RunStatus.FAILED_PRECONDITION and result.reason == FailureReason.DATA_COVERAGE_GAP:
            # Check promotion mode
            if os.getenv("REQUIRE_GOLDEN_DATA") == "1":
                # PROMOTION MODE: Fail explicitly (blocks promotion)
                pytest.fail(
                    "Golden data missing (promotion blocked). "
                    f"Expected APP M5 data for range: {result.details.get('gap', 'unknown gap')}. "
                    "Set REQUIRE_GOLDEN_DATA=1 to enforce this in CI/CD."
                )
            
            # DEV MODE: Skip (allows development without full dataset)
            pytest.skip(f"APP M5 data not available: {result.details.get('gap', 'unknown gap')}")
        
        assert result.status == RunStatus.SUCCESS, \
            f"Golden Atom must SUCCESS. Got: {result.status.value}, reason: {result.reason}"
        
        # Verify artifacts exist
        run_dir = tmp_path / "golden_atom_app_m5"
        assert run_dir.exists(), "Run directory must exist"
        
        assert (run_dir / "run_meta.json").exists(), "run_meta.json must exist"
        assert (run_dir / "run_result.json").exists(), "run_result.json must exist"
        assert (run_dir / "run_manifest.json").exists(), "run_manifest.json must exist"
        assert (run_dir / "coverage_check.json").exists(), "coverage_check.json must exist"
        
        # Verify manifest structure
        with open(run_dir / "run_manifest.json") as f:
            manifest = json.load(f)
        
        assert manifest["identity"]["market_tz"] == "America/New_York"
        assert manifest["strategy"]["key"] == "inside_bar"
        assert manifest["strategy"]["impl_version"] == "1.0.0"
        assert manifest["strategy"]["profile_version"] == "default"
        assert manifest["data"]["symbol"] == "APP"
        assert manifest["data"]["base_tf_used"] == "M5"
        assert manifest["result"]["run_status"] == "success"
        
        # Verify coverage was SUFFICIENT (not GAP_DETECTED)
        coverage = manifest["gates"]["coverage"]
        assert coverage is not None, "Coverage gate must run"
        assert coverage["status"] == "sufficient", \
            f"Coverage must be SUFFICIENT for Golden Atom. Got: {coverage['status']}"
        
        # NOTE: Deterministic metrics assertions would go here
        # For minimal_pipeline (which doesn't execute strategy yet), we verify structure
        # Once real strategy execution is added, assert:
        # - signals_count in expected range (e.g., 10-50)
        # - trades_count in expected range
        # - equity_curve exists with expected length
        # - metrics fields are numeric
    
    @pytest.mark.golden
    def test_golden_atom_manifest_is_reproducible(self, tmp_path):
        """
        Verify Golden Atom manifest contains full reproducibility context.
        
        Manifest must have:
        - Exact params
        - Git commit hash
        - Data spec (symbol, TF, ranges)
        - Coverage + SLA results
        """
        result = minimal_backtest_with_gates(
            run_id="golden_reproducible",
            symbol="APP",
            timeframe="M5",
            requested_end="2025-12-15",
            lookback_days=100,
            strategy_params={"atr_period": 14},
            artifacts_root=tmp_path
        )
        
        # Skip if data not available (with promotion policy)
        import os
        if result.status == RunStatus.FAILED_PRECONDITION and result.reason == FailureReason.DATA_COVERAGE_GAP:
            if os.getenv("REQUIRE_GOLDEN_DATA") == "1":
                pytest.fail(
                    "Golden data missing (promotion blocked). "
                    f"Required for reproducibility test: {result.details.get('gap')}"
                )
            pytest.skip(f"APP M5 data not available: {result.details.get('gap', 'unknown gap')}")

        
        run_dir = tmp_path / "golden_reproducible"
        manifest_path = run_dir / "run_manifest.json"
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Verify reproducibility context
        assert "identity" in manifest
        assert "commit_hash" in manifest["identity"]  # Git SHA for exact code version
        
        assert "strategy" in manifest
        assert manifest["strategy"]["impl_version"] is not None
        assert manifest["strategy"]["profile_version"] is not None
        
        assert "params" in manifest
        assert manifest["params"]["atr_period"] == 14
        
        assert "data" in manifest
        assert manifest["data"]["symbol"] == "APP"
        assert manifest["data"]["requested_tf"] == "M5"
        assert manifest["data"]["base_tf_used"] == "M5"
        assert manifest["data"]["requested_range"]["lookback_days"] == 100
        
        assert "gates" in manifest
        assert manifest["gates"]["coverage"] is not None
        
        assert "result" in manifest
        assert manifest["result"]["run_status"] == "success"
    
    @pytest.mark.golden
    def test_golden_atom_fails_gracefully_on_coverage_gap(self, tmp_path):
        """
        Golden Atom with non-existent symbol should fail as FAILED_PRECONDITION,
        not ERROR.
        
        This verifies gates work correctly even for Golden config.
        """
        result = minimal_backtest_with_gates(
            run_id="golden_gap",
            symbol="NONEXISTENT_GOLDEN",  # Trigger coverage gap
            timeframe="M5",
            requested_end="2025-12-15",
            lookback_days=100,
            strategy_params={"atr_period": 14},
            artifacts_root=tmp_path
        )
        
        # Should be FAILED_PRECONDITION (not ERROR)
        assert result.status == RunStatus.FAILED_PRECONDITION
        assert result.reason is not None
        
        # Manifest should still exist
        run_dir = tmp_path / "golden_gap"
        assert (run_dir / "run_manifest.json").exists()
        
        with open(run_dir / "run_manifest.json") as f:
            manifest = json.load(f)
        
        assert manifest["result"]["run_status"] == "failed_precondition"
        assert manifest["gates"]["coverage"]["status"] in ["gap_detected", "fetch_failed"]


@pytest.fixture
def golden_atom_config():
    """
    Golden Atom configuration fixture.
    
    Use this to ensure consistent config across tests.
    """
    return {
        "symbol": "APP",
        "timeframe": "M5",
        "lookback_days": 100,
        "strategy_params": {
            "atr_period": 14,
            "min_mother_bar_size_atr_multiple": 1.5,
            "require_close_beyond_mother": True,
            "risk_reward_ratio": 2.0,
            "lookback_candles": 50,
            "max_pattern_age_candles": 5
        },
        "impl_version": "1.0.0",
        "profile_version": "default"
    }
