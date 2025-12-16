"""
Artifacts Manager

Manages backtest run artifacts directory and manifest files.

CRITICAL INVARIANT:
- artifacts/backtests/<run_id>/ ALWAYS created (even on crash/error)
- run_meta.json written at START
- run_result.json written at END (always)
- error_stacktrace.txt + error_id only on ERROR

ARCHITECTURE:
- Engine/Service layer (UI-independent)
- Fail-safe: create artifacts even on exceptions
- Structured manifests for audit trail
"""

import logging
import json
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import asdict

from backtest.services.run_status import RunResult, RunStatus

logger = logging.getLogger(__name__)


class ArtifactsManager:
    """
    Manages backtest run artifacts.
    
    Ensures artifacts directory and manifests are ALWAYS created,
    even if run fails or crashes.
    """
    
    def __init__(self, artifacts_root: Path = None):
        """
        Args:
            artifacts_root: Root artifacts directory (default: artifacts/backtests/)
        """
        if artifacts_root is None:
            # Default: artifacts/backtests/ relative to project root
            artifacts_root = Path("artifacts/backtests")
        
        self.artifacts_root = Path(artifacts_root)
        self.current_run_dir: Optional[Path] = None
        self.run_id: Optional[str] = None
        self.backtests_dir = self.artifacts_root # Assuming artifacts_root is already the backtests root
    
    def create_run_dir(self, run_id: str) -> "RunContext":
        """
        Create the run directory and return RunContext.
        
        Args:
            run_id: Unique identifier for this run
            
        Returns:
            RunContext with run_id, run_name, and absolute run_dir path
            
        Raises:
            ValueError: If directory already exists
        """
        from .run_context import RunContext
        
        run_dir = self.backtests_dir / run_id
        
        if run_dir.exists():
            raise ValueError(f"Run directory already exists: {run_dir}")
        
        run_dir.mkdir(parents=True)
        logger.info(f"Created run directory: {run_dir.relative_to(self.artifacts_root)}")
        
        # Return RunContext as SSOT
        return RunContext(
            run_id=run_id,
            run_name=run_id,  # In current impl, run_name == run_id
            run_dir=run_dir.absolute()
        )
    
    def write_run_meta(
        self,
        strategy: str,
        symbols: list,
        timeframe: str,
        params: Dict[str, Any],
        requested_end: str,
        lookback_days: int,
        commit_hash: Optional[str] = None,
        market_tz: str = "America/New_York",
        # Manifest-specific params
        impl_version: str = "1.0.0",
        profile_version: str = "default"
    ):
        """
        Write run metadata at START (before execution).
        
        Also initializes manifest writer if manifest writing is enabled.
        
        Args:
            strategy: Strategy key (e.g., "inside_bar")
            symbols: List of symbols
            timeframe: M1/M5/M15
            params: Strategy parameters dict
            requested_end: Requested end date ISO format
            lookback_days: Lookback in days
            commit_hash: Git commit hash (optional)
            market_tz: Market timezone
            impl_version: Strategy implementation version
            profile_version: Strategy profile version
        """
        if not self.current_run_dir:
            raise RuntimeError("create_run_dir() must be called first")
        
        run_meta = {
            "run_id": self.run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "strategy": {
                "key": strategy,
                "impl_version": impl_version,
                "profile_version": profile_version
            },
            "params": params,
            "data": {
                "symbols": symbols,
                "timeframe": timeframe,
                "requested_end": requested_end,
                "lookback_days": lookback_days
            },
            "commit_hash": commit_hash,
            "market_tz": market_tz
        }
        
        meta_path = self.current_run_dir / "run_meta.json"
        with open(meta_path, 'w') as f:
            json.dump(run_meta, f, indent=2)
        
        logger.info(f"Wrote run_meta.json: {meta_path}")
        
        # Initialize manifest writer
        try:
            from backtest.services.manifest_writer import ManifestWriter
            
            self.manifest_writer = ManifestWriter(self.current_run_dir)
            
            # Write initial manifest
            self.manifest_writer.write_initial_manifest(
                run_id=self.run_id,
                strategy_key=strategy,
                impl_version=impl_version,
                profile_version=profile_version,
                params=params,
                symbol=symbols[0] if symbols else "UNKNOWN",  # TODO: handle multi-symbol
                requested_tf=timeframe,
                base_tf=timeframe,  # For now, same as requested
                lookback_days=lookback_days,
                requested_end=requested_end
            )
        except Exception as e:
            logger.warning(f"Failed to initialize manifest writer: {e}")
            self.manifest_writer = None
    
    def write_run_result(self, run_result: RunResult, artifacts_produced: Optional[list] = None):
        """
        Write run result at END (always called, even on failure).
        
        Also finalizes manifest if manifest writer is initialized.
        
        Args:
            run_result: RunResult DTO
            artifacts_produced: List of artifact filenames produced (optional)
        """
        if not self.current_run_dir:
            raise RuntimeError("create_run_dir() must be called first")
        
        result_data = {
            "run_id": run_result.run_id,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": run_result.status.value,
            "reason": run_result.reason.value if run_result.reason else None,
            "details": run_result.details,
            "error_id": run_result.error_id
        }
        
        result_path = self.current_run_dir / "run_result.json"
        with open(result_path, 'w') as f:
            json.dump(result_data, f, indent=2)
        
        logger.info(f"Wrote run_result.json: {result_path} (status={run_result.status.value})")
        
        # Finalize manifest
        if hasattr(self, 'manifest_writer') and self.manifest_writer is not None:
            try:
                self.manifest_writer.finalize_manifest(run_result, artifacts_produced)
            except Exception as e:
                logger.error(f"Manifest finalization failed: {e}")
                # Do not raise - must not crash run_result writing
    
    def write_error_stacktrace(self, exception: Exception, error_id: str):
        """
        Write error stacktrace and error_id (only on ERROR status).
        
        Args:
            exception: The exception that occurred
            error_id: Error correlation ID
        """
        if not self.current_run_dir:
            raise RuntimeError("create_run_dir() must be called first")
        
        stacktrace_path = self.current_run_dir / "error_stacktrace.txt"
        with open(stacktrace_path, 'w') as f:
            f.write(f"Error ID: {error_id}\n")
            f.write(f"Exception Type: {type(exception).__name__}\n")
            f.write(f"Exception Message: {str(exception)}\n\n")
            f.write("Stacktrace:\n")
            f.write(traceback.format_exc())
        
        logger.error(f"Wrote error_stacktrace.txt: {stacktrace_path} (error_id={error_id})")
    
    def write_coverage_check_result(self, coverage_result: Any):
        """
        Write coverage check result (for audit trail).
        
        Args:
            coverage_result: CoverageCheckResult DTO
        """
        if not self.current_run_dir:
            raise RuntimeError("create_run_dir() must be called first")
        
        coverage_path = self.current_run_dir / "coverage_check.json"
        with open(coverage_path, 'w') as f:
            json.dump(coverage_result.to_dict(), f, indent=2)
        
        logger.info(f"Wrote coverage_check.json: {coverage_path}")
    
    def write_sla_check_result(self, sla_result: Any):
        """
        Write SLA check result (for audit trail).
        
        Args:
            sla_result: SLAResult DTO
        """
        if not self.current_run_dir:
            raise RuntimeError("create_run_dir() must be called first")
        
        sla_path = self.current_run_dir / "sla_check.json"
        # SLAResult will be implemented in Phase 3
        # For now, accept dict
        if hasattr(sla_result, 'to_dict'):
            data = sla_result.to_dict()
        else:
            data = sla_result
        
        with open(sla_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Wrote sla_check.json: {sla_path}")
    
    def get_run_dir(self) -> Path:
        """Get current run directory."""
        if not self.current_run_dir:
            raise RuntimeError("create_run_dir() must be called first")
        return self.current_run_dir
