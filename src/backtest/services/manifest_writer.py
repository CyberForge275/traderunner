"""
Manifest Writer

Creates comprehensive run manifest for reproducibility and auditability.

CRITICAL INVARIANTS:
- run_manifest.json written for ALL outcomes (SUCCESS/FAILED_PRECONDITION/ERROR)
- Initial manifest written after run_meta.json
- Finalized manifest written at end (with run_result)
- Manifest writing failures NEVER crash run_result writing

MANIFEST PURPOSE:
- Reproducibility: Full context to recreate exact run
- Auditability: Complete trail of what happened and why
- Promotion: Pre-Paper can reuse atom definition
- Versioning: Strategy impl/profile versions tracked
"""

import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import asdict

from backtest.services.run_status import RunResult

logger = logging.getLogger(__name__)


class ManifestWriter:
    """
    Writes run manifest for Backtest-Atom.

    Manifest contains:
    1. Identity (run_id, timestamp, commit, market_tz)
    2. Strategy Version (impl_version, profile_version)
    3. Params (exact config)
    4. Data Spec (symbol, TF, ranges, paths, hashes)
    5. Gate Results (coverage + SLA)
    6. Result (status, reason, artifacts)
    """

    def __init__(self, run_dir: Path):
        """
        Args:
            run_dir: Run artifacts directory
        """
        self.run_dir = Path(run_dir)
        self.manifest_path = self.run_dir / "run_manifest.json"
        self.manifest: Dict[str, Any] = {}

    def write_initial_manifest(
        self,
        run_id: str,
        strategy_key: str,
        impl_version: str,
        profile_version: str,
        params: Dict[str, Any],
        symbol: str,
        requested_tf: str,
        base_tf: str,
        lookback_days: int,
        requested_end: str,
        universe_path: Optional[str] = None,
        intraday_paths: Optional[List[str]] = None
    ):
        """
        Write initial manifest after run_meta.json.

        Contains all input context except gate results.
        """
        try:
            # Get git commit hash
            commit_hash = self._get_git_commit()

            self.manifest = {
                # 1. Identity
                "identity": {
                    "run_id": run_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "commit_hash": commit_hash,
                    "market_tz": "America/New_York"  # IMMUTABLE
                },

                # 2. Strategy Version (Backtest-Atom SSOT)
                "strategy": {
                    "key": strategy_key,
                    "impl_version": impl_version,
                    "profile_version": profile_version
                },

                # 3. Params (exact config from run)
                "params": params,

                # 4. Data Spec
                "data": {
                    "symbol": symbol,
                    "requested_tf": requested_tf,
                    "base_tf_used": base_tf,  # Important for SLA interpretation
                    "requested_range": {
                        "lookback_days": lookback_days,
                        "requested_end_date": requested_end
                    },
                    "effective_range": None,  # Filled after execution
                    "inputs": {
                        "universe_parquet": universe_path,
                        "intraday_source_paths": intraday_paths or []
                    }
                },

                # 5. Gate Results (filled during execution)
                "gates": {
                    "coverage": None,
                    "sla": None
                },

                # 6. Result (filled at end)
                "result": {
                    "run_status": None,
                    "failure_reason": None,
                    "failure_details": None,
                    "error_id": None,
                    "artifacts_index": []
                }
            }

            # Write initial version
            self._write_manifest()
            logger.info(f"Wrote initial manifest: {self.manifest_path}")

        except Exception as e:
            logger.error(f"Failed to write initial manifest: {e}", exc_info=True)
            # Do not raise - manifest writing failures should not crash run

    def update_coverage_gate(self, coverage_result):
        """
        Update manifest with coverage gate results.

        Args:
            coverage_result: CoverageCheckResult DTO
        """
        try:
            self.manifest["gates"]["coverage"] = coverage_result.to_dict()
            self._write_manifest()
        except Exception as e:
            logger.error(f"Failed to update coverage gate in manifest: {e}")

    def update_sla_gate(self, sla_result):
        """
        Update manifest with SLA gate results.

        Args:
            sla_result: SLAResult DTO
        """
        try:
            self.manifest["gates"]["sla"] = sla_result.to_dict()
            self._write_manifest()
        except Exception as e:
            logger.error(f"Failed to update SLA gate in manifest: {e}")

    def update_effective_range(self, start_ts: str, end_ts: str):
        """
        Update effective data range (actual data used).

        Args:
            start_ts: Start timestamp ISO format with TZ
            end_ts: End timestamp ISO format with TZ
        """
        try:
            self.manifest["data"]["effective_range"] = {
                "start_ts": start_ts,
                "end_ts": end_ts
            }
            self._write_manifest()
        except Exception as e:
            logger.error(f"Failed to update effective range in manifest: {e}")

    def finalize_manifest(
        self,
        run_result: RunResult,
        artifacts_produced: Optional[List[str]] = None
    ):
        """
        Finalize manifest at end (called with run_result.json).

        Args:
            run_result: RunResult DTO
            artifacts_produced: List of artifact file names produced
        """
        try:
            # Update result section
            self.manifest["result"] = {
                "run_status": run_result.status.value,
                "failure_reason": run_result.reason.value if run_result.reason else None,
                "failure_details": run_result.details,
                "error_id": run_result.error_id,
                "artifacts_index": artifacts_produced or []
            }

            # Write final version
            self._write_manifest()
            logger.info(f"Finalized manifest: {self.manifest_path}")

        except Exception as e:
            logger.error(f"Failed to finalize manifest: {e}", exc_info=True)
            # Do not raise - manifest finalization must not crash run_result writing

    def _write_manifest(self):
        """Write manifest to file (internal helper)."""
        with open(self.manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2, sort_keys=True)  # sort_keys for diff-friendly

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=True,
                timeout=2
            )
            return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Failed to get git commit: {e}")
            return None
