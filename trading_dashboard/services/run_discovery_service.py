"""
RunDiscoveryService - Manifest-based backtest run discovery.

Discovers backtest runs by reading artifacts (run_manifest.json, run_meta.json),
never by parsing directory names. Replaces legacy run_log.json discovery.

INVARIANTS:
- Never parse symbol/timeframe/strategy from directory names
- Prefer run_manifest.json over run_meta.json
- Include corrupt runs with parse_error (never silently drop)
- Load steps from run_steps.jsonl if present
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class BacktestRunSummary:
    """Summary of a discovered backtest run."""

    run_id: str
    run_dir: Path  # Absolute path to run directory
    strategy_key: str
    symbols: List[str]
    requested_tf: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str  # SUCCESS, FAILED_PRECONDITION, ERROR, CORRUPT
    failure_reason: Optional[str] = None
    parse_error: Optional[str] = None  # Only for CORRUPT runs
    has_steps: bool = False
    steps_count: int = 0


class RunDiscoveryService:
    """
    Discover backtest runs from artifacts directory.

    Discovery priority:
    1. run_manifest.json (most complete, preferred)
    2. run_meta.json (fallback)
    3. Ignore directory if no artifacts found
    4. Mark as CORRUPT if JSON parse fails
    """

    def __init__(self, artifacts_root: Optional[Path] = None):
        """
        Initialize discovery service.

        Args:
            artifacts_root: Root directory containing backtest runs.
                           Defaults to current working directory.
        """
        if artifacts_root is None:
            from trading_dashboard.config import BACKTESTS_DIR
            artifacts_root = BACKTESTS_DIR

        self.artifacts_root = Path(artifacts_root)

        # Diagnostics
        self._discovered_count = 0
        self._corrupt_count = 0
        self._skipped_count = 0
        self._skipped_reasons: List[Dict[str, str]] = []

    def discover(self) -> List[BacktestRunSummary]:
        """
        Discover all backtest runs from artifacts directory.

        Returns:
            List of BacktestRunSummary, sorted by started_at descending.
        """
        # Reset diagnostics
        self._discovered_count = 0
        self._corrupt_count = 0
        self._skipped_count = 0
        self._skipped_reasons = []

        runs: List[BacktestRunSummary] = []

        if not self.artifacts_root.exists():
            logger.warning(f"Artifacts root does not exist: {self.artifacts_root}")
            return runs

        logger.info(f"🔍 Discovering runs from: {self.artifacts_root}")

        for entry in sorted(self.artifacts_root.iterdir()):
            if not entry.is_dir():
                continue

            # Skip legacy runner directories (run_*)
            if entry.name.startswith("run_"):
                self._skip(entry.name, "legacy_runner_dir")
                continue

            run_summary = self._discover_run(entry)
            if run_summary is not None:
                runs.append(run_summary)

        # Sort by started_at descending (most recent first)
        runs.sort(key=lambda r: r.started_at, reverse=True)

        logger.info(
            f"✅ Discovery complete: {self._discovered_count} discovered, "
            f"{self._corrupt_count} corrupt, {self._skipped_count} skipped"
        )

        return runs

    def _discover_run(self, run_dir: Path) -> Optional[BacktestRunSummary]:
        """
        Discover a single run from its directory.

        Args:
            run_dir: Path to run directory

        Returns:
            BacktestRunSummary if artifacts found, None if no artifacts
        """
        run_id = run_dir.name

        # Check for new-pipeline artifacts
        manifest_file = run_dir / "run_manifest.json"
        meta_file = run_dir / "run_meta.json"
        result_file = run_dir / "run_result.json"
        steps_file = run_dir / "run_steps.jsonl"

        # Prefer manifest, fallback to meta
        if manifest_file.exists():
            return self._parse_from_manifest(run_dir, manifest_file, result_file, steps_file)
        elif meta_file.exists():
            return self._parse_from_meta(run_dir, meta_file, result_file, steps_file)
        else:
            # No artifacts found - skip
            self._skip(run_id, "no_artifacts")
            return None

    def _parse_from_manifest(
        self,
        run_dir: Path,
        manifest_file: Path,
        result_file: Path,
        steps_file: Path
    ) -> BacktestRunSummary:
        """Parse run from run_manifest.json (preferred)."""
        run_id = run_dir.name

        try:
            with open(manifest_file) as f:
                manifest = json.load(f)

            # Extract from manifest (actual structure, not expected structure)
            identity = manifest.get("identity", {})
            execution = manifest.get("execution", {})
            outcome = manifest.get("result", {})  # "result" not "outcome"
            strategy_section = manifest.get("strategy", {})
            data_section = manifest.get("data", {})

            # Parse started_at
            started_at_str = execution.get("started_at") or identity.get("timestamp_utc")
            if started_at_str:
                started_at = datetime.fromisoformat(started_at_str)
            else:
                # Fallback to directory mtime (make UTC-aware)
                from datetime import timezone
                started_at = datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc)

            # Parse finished_at (might not exist in manifest)
            finished_at = None

            # Get status from result section
            status = outcome.get("run_status", "unknown").upper()
            failure_reason = outcome.get("failure_reason")

            # Get strategy key from strategy section
            strategy_key = strategy_section.get("key", "unknown")

            # Get symbols and TF from data section
            # Note: manifest has "symbol" (singular) not "symbols" (plural)
            symbol = data_section.get("symbol")
            symbols = [symbol] if symbol else []
            requested_tf = data_section.get("requested_tf", "unknown")

            # Load steps if available
            has_steps, steps_count = self._load_steps_info(steps_file)

            self._discovered_count += 1

            return BacktestRunSummary(
                run_id=run_id,
                run_dir=run_dir.absolute(),
                strategy_key=strategy_key,
                symbols=symbols,
                requested_tf=requested_tf,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                failure_reason=failure_reason,
                has_steps=has_steps,
                steps_count=steps_count
            )

        except Exception as e:
            from datetime import timezone
            logger.error(f"Failed to parse manifest for {run_id}: {e}")
            self._corrupt_count += 1
            self._discovered_count += 1

            return BacktestRunSummary(
                run_id=run_id,
                run_dir=run_dir.absolute(),
                strategy_key="unknown",
                symbols=[],
                requested_tf="unknown",
                started_at=datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc),
                finished_at=None,
                status="CORRUPT",
                parse_error=f"Manifest parse error: {str(e)}"
            )

    def _parse_from_meta(
        self,
        run_dir: Path,
        meta_file: Path,
        result_file: Path,
        steps_file: Path
    ) -> BacktestRunSummary:
        """Parse run from run_meta.json (fallback)."""
        run_id = run_dir.name

        try:
            from datetime import timezone

            with open(meta_file) as f:
                meta = json.load(f)

            # Parse metadata
            strategy = meta.get("strategy", {})
            data = meta.get("data", {})

            started_at_str = meta.get("started_at")
            if started_at_str:
                started_at = datetime.fromisoformat(started_at_str)
            else:
                started_at = datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc)

            # Try to get status from run_result.json
            status = "unknown"
            finished_at = None
            failure_reason = None

            if result_file.exists():
                try:
                    with open(result_file) as f:
                        result = json.load(f)
                    status = result.get("status", "unknown").upper()
                    failure_reason = result.get("reason")
                    finished_at_str = result.get("finished_at")
                    if finished_at_str:
                        finished_at = datetime.fromisoformat(finished_at_str)
                except Exception as e:
                    logger.warning(f"Failed to parse run_result.json for {run_id}: {e}")

            # Load steps if available
            has_steps, steps_count = self._load_steps_info(steps_file)

            self._discovered_count += 1

            return BacktestRunSummary(
                run_id=run_id,
                run_dir=run_dir.absolute(),
                strategy_key=strategy.get("key", "unknown"),
                symbols=data.get("symbols", []),
                requested_tf=data.get("timeframe", "unknown"),
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                failure_reason=failure_reason,
                has_steps=has_steps,
                steps_count=steps_count
            )

        except Exception as e:
            from datetime import timezone
            logger.error(f"Failed to parse meta for {run_id}: {e}")
            self._corrupt_count += 1
            self._discovered_count += 1

            return BacktestRunSummary(
                run_id=run_id,
                run_dir=run_dir.absolute(),
                strategy_key="unknown",
                symbols=[],
                requested_tf="unknown",
                started_at=datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc),
                finished_at=None,
                status="CORRUPT",
                parse_error=f"Meta parse error: {str(e)}"
            )

    def _load_steps_info(self, steps_file: Path) -> tuple[bool, int]:
        """
        Load step information from run_steps.jsonl.

        Returns:
            (has_steps, steps_count)
        """
        if not steps_file.exists():
            return False, 0

        try:
            steps = []
            with open(steps_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        steps.append(json.loads(line))

            # Count unique step_index values (not total events)
            unique_steps = len(set(s.get("step_index") for s in steps if "step_index" in s))
            return True, unique_steps

        except Exception as e:
            logger.warning(f"Failed to load steps from {steps_file}: {e}")
            return False, 0

    def _skip(self, dir_name: str, reason: str):
        """Record a skipped directory."""
        self._skipped_count += 1
        self._skipped_reasons.append({"dir_name": dir_name, "reason": reason})

        # Keep only last 20 skipped reasons
        if len(self._skipped_reasons) > 20:
            self._skipped_reasons = self._skipped_reasons[-20:]

    def get_diagnostics(self) -> Dict[str, Any]:
        """
        Get discovery diagnostics for debugging.

        Returns:
            Dictionary with discovered_count, corrupt_count, skipped_count, skipped_reasons
        """
        return {
            "discovered_count": self._discovered_count,
            "corrupt_count": self._corrupt_count,
            "skipped_count": self._skipped_count,
            "skipped_reasons": self._skipped_reasons,
            "artifacts_root": str(self.artifacts_root)
        }
