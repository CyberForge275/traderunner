"""
BacktestDetailsService - SSOT reader for run details from manifests.

Reads from run_manifest.json (preferred) or run_meta.json+run_result.json (fallback).
Never requires run_log.json. Returns structured data (no exceptions to UI).
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RunDetails:
    """Complete details for a backtest run."""

    run_id: str
    status: str  # SUCCESS, FAILED_PRECONDITION, ERROR, CORRUPT, INCOMPLETE
    strategy_key: str
    symbols: List[str]
    requested_tf: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    error_message: Optional[str] = None  # For CORRUPT/INCOMPLETE
    source: str = "unknown"  # manifest, meta+result, error


@dataclass
class RunStep:
    """Single pipeline step."""

    step_index: int
    step_name: str
    status: str  # started, completed, failed, skipped
    timestamp: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    details: Optional[str] = None


class BacktestDetailsService:
    """
    Load backtest run details from artifacts (SSOT).

    Priority:
    1. run_manifest.json (most complete)
    2. run_meta.json + run_result.json (fallback)
    3. Error structure if corrupt/missing
    """

    def __init__(self, artifacts_root: Optional[Path] = None):
        """
        Initialize service.

        Args:
            artifacts_root: Root directory containing backtest runs
        """
        if artifacts_root is None:
            from trading_dashboard.config import BACKTESTS_DIR
            artifacts_root = BACKTESTS_DIR

        self.artifacts_root = Path(artifacts_root)

    def load_summary(self, run_id: str) -> RunDetails:
        """
        Load run summary from artifacts.

        Args:
            run_id: Run identifier (directory name)

        Returns:
            RunDetails with all available information
        """
        run_dir = self.artifacts_root / run_id

        if not run_dir.exists():
            return RunDetails(
                run_id=run_id,
                status="INCOMPLETE",
                strategy_key="unknown",
                symbols=[],
                requested_tf="unknown",
                error_message=f"Run directory not found: {run_dir}",
                source="error"
            )

        manifest_file = run_dir / "run_manifest.json"
        meta_file = run_dir / "run_meta.json"
        result_file = run_dir / "run_result.json"

        # Try manifest first
        if manifest_file.exists():
            return self._load_from_manifest(run_id, run_dir, manifest_file, result_file)
        elif meta_file.exists():
            return self._load_from_meta(run_id, run_dir, meta_file, result_file)
        else:
            return RunDetails(
                run_id=run_id,
                status="INCOMPLETE",
                strategy_key="unknown",
                symbols=[],
                requested_tf="unknown",
                error_message="No artifacts found (no run_manifest.json or run_meta.json)",
                source="error"
            )

    def _load_from_manifest(
        self,
        run_id: str,
        run_dir: Path,
        manifest_file: Path,
        result_file: Path,
    ) -> RunDetails:
        """Load from run_manifest.json."""
        try:
            with open(manifest_file) as f:
                manifest = json.load(f)

            identity = manifest.get("identity", {})
            strategy_section = manifest.get("strategy", {})
            data_section = manifest.get("data", {})
            result_section = manifest.get("result", {})

            # Parse timestamps
            started_at_str = identity.get("timestamp_utc")
            started_at = datetime.fromisoformat(started_at_str) if started_at_str else None

            # Status from manifest result section, with fallback to run_result.json.
            status = result_section.get("run_status")
            failure_reason = result_section.get("failure_reason")
            if not status and result_file.exists():
                try:
                    with open(result_file) as f:
                        result = json.load(f)
                    status = result.get("status")
                    if not failure_reason:
                        failure_reason = result.get("reason")
                except Exception as e:
                    logger.warning(f"Failed to parse run_result.json for {run_id}: {e}")
            status = str(status or "unknown").upper()

            # Extract symbol (singular in manifest)
            symbol = data_section.get("symbol")
            symbols = [symbol] if symbol else []

            return RunDetails(
                run_id=run_id,
                status=status,
                strategy_key=strategy_section.get("key", "unknown"),
                symbols=symbols,
                requested_tf=data_section.get("requested_tf", "unknown"),
                started_at=started_at,
                finished_at=None,  # Not in manifest
                failure_reason=failure_reason,
                source="manifest"
            )

        except Exception as e:
            logger.error(f"Failed to parse manifest for {run_id}: {e}")
            return RunDetails(
                run_id=run_id,
                status="CORRUPT",
                strategy_key="unknown",
                symbols=[],
                requested_tf="unknown",
                error_message=f"Manifest parse error: {str(e)}",
                source="error"
            )

    def _load_from_meta(
        self,
        run_id: str,
        run_dir: Path,
        meta_file: Path,
        result_file: Path
    ) -> RunDetails:
        """Load from run_meta.json + run_result.json."""
        try:
            with open(meta_file) as f:
                meta = json.load(f)

            strategy = meta.get("strategy", {})
            data = meta.get("data", {})

            # Parse started_at
            started_at_str = meta.get("started_at")
            started_at = datetime.fromisoformat(started_at_str) if started_at_str else None

            # Try to load result
            status = "UNKNOWN"
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

            return RunDetails(
                run_id=run_id,
                status=status,
                strategy_key=strategy.get("key", "unknown"),
                symbols=data.get("symbols", []),
                requested_tf=data.get("timeframe", "unknown"),
                started_at=started_at,
                finished_at=finished_at,
                failure_reason=failure_reason,
                source="meta+result"
            )

        except Exception as e:
            logger.error(f"Failed to parse meta for {run_id}: {e}")
            return RunDetails(
                run_id=run_id,
                status="CORRUPT",
                strategy_key="unknown",
                symbols=[],
                requested_tf="unknown",
                error_message=f"Meta parse error: {str(e)}",
                source="error"
            )

    def load_steps(self, run_id: str) -> List[RunStep]:
        """
        Load pipeline steps from run_steps.jsonl.

        Args:
            run_id: Run identifier

        Returns:
            List of RunStep, sorted by step_index
        """
        run_dir = self.artifacts_root / run_id
        steps_file = run_dir / "run_steps.jsonl"

        if not steps_file.exists():
            logger.debug(f"No run_steps.jsonl for {run_id}")
            return []

        try:
            # Read all events
            events = []
            with open(steps_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))

            # Group by step_index
            steps_dict = {}
            for event in events:
                step_idx = event.get("step_index")
                if step_idx is None:
                    continue

                if step_idx not in steps_dict:
                    steps_dict[step_idx] = {
                        "step_index": step_idx,
                        "step_name": event.get("step_name"),
                        "status": event.get("status"),
                        "started_at": None,
                        "completed_at": None,
                        "details": event.get("details")
                    }

                # Update status and timestamps
                status = event.get("status")
                timestamp = event.get("timestamp")

                if status == "started" and timestamp:
                    steps_dict[step_idx]["started_at"] = timestamp
                elif status in ["completed", "failed", "skipped"] and timestamp:
                    steps_dict[step_idx]["completed_at"] = timestamp
                    steps_dict[step_idx]["status"] = status

            # Convert to RunStep objects
            steps = []
            for step_data in steps_dict.values():
                # Compute duration
                duration = None
                if step_data["started_at"] and step_data["completed_at"]:
                    try:
                        start = datetime.fromisoformat(step_data["started_at"])
                        end = datetime.fromisoformat(step_data["completed_at"])
                        duration = (end - start).total_seconds()
                    except Exception:
                        pass

                # Use most recent timestamp
                timestamp = step_data["completed_at"] or step_data["started_at"]
                ts = datetime.fromisoformat(timestamp) if timestamp else None

                steps.append(RunStep(
                    step_index=step_data["step_index"],
                    step_name=step_data["step_name"],
                    status=step_data["status"],
                    timestamp=ts,
                    duration_seconds=duration,
                    details=step_data["details"]
                ))

            # Sort by step_index
            steps.sort(key=lambda s: s.step_index)
            return steps

        except Exception as e:
            logger.error(f"Failed to load steps for {run_id}: {e}")
            return []
