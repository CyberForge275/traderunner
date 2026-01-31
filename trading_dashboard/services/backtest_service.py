"""Backtest Service - Background job management for running backtests."""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add traderunner src to path for imports
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))
os.environ.setdefault("PYTHONPATH", str(SRC))


class BacktestService:
    """Manages background backtest execution using threading.

    This service allows running backtests without blocking the Dash UI.
    Jobs are tracked in memory with status updates.
    """

    def __init__(self):
        self.running_jobs: Dict[str, Dict] = {}  # job_id -> job metadata
        self.completed_jobs: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def start_backtest(
        self,
        run_name: str,
        strategy: str,
        symbols: List[str],
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        config_params: Optional[Dict] = None
    ) -> str:
        """Start a backtest in background thread.

        Args:
            run_name: Name for the backtest run
            strategy: Strategy identifier (e.g., "inside_bar")
            symbols: List of symbols to backtest
            timeframe: Candle timeframe (e.g., "M5", "D1")
            start_date: Start date for backtest (ISO format YYYY-MM-DD)
            end_date: End date for backtest (ISO format YYYY-MM-DD)
            config_params: Optional additional configuration

        Returns:
            job_id: Unique identifier for tracking this job
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_id = f"{run_name}_{timestamp}"
        from axiom_bt.utils.trace import trace_ui
        trace_ui(
            step="service_start_backtest",
            run_id=run_name,
            strategy_id=strategy,
            file=__file__,
            func="start_backtest",
            extra={
                "job_id": job_id,
                "symbols": symbols,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
                "config_params": config_params,
            },
        )

        with self._lock:
            self.running_jobs[job_id] = {
                "status": "running",
                "run_name": run_name,
                "strategy": strategy,
                "symbols": symbols,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
                "started_at": datetime.now().isoformat(),
                "progress": "Initializing...",
            }

        # Start background thread
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(job_id, run_name, strategy, symbols, timeframe, start_date, end_date, config_params),
            daemon=True
        )
        thread.start()

        return job_id

    def _run_pipeline(
        self,
        job_id: str,
        run_name: str,
        strategy: str,
        symbols: List[str],
        timeframe: str,
        start_date: Optional[str],
        end_date: Optional[str],
        config_params: Optional[Dict]
    ):
        """Execute pipeline in background thread.

        This method runs the full backtest pipeline:
        1. Fetch intraday data
        2. Generate signals
        3. Export orders
        4. Run backtest simulation
        """
        try:
            # Update progress
            self._update_job_progress(job_id, "Loading pipeline configuration...")

            # NEW path (ONLY) - SSOT modular pipeline
            from .new_pipeline_adapter import create_new_adapter

            def update_progress(msg: str):
                self._update_job_progress(job_id, msg)

            adapter = create_new_adapter(progress_callback=update_progress)
            from axiom_bt.utils.trace import trace_ui
            trace_ui(
                step="service_run_pipeline_start",
                run_id=run_name,
                strategy_id=strategy,
                file=__file__,
                func="_run_pipeline",
                extra={"job_id": job_id},
            )


            # Execute backtest
            result = adapter.execute_backtest(
                run_name=run_name,
                strategy=strategy,
                symbols=symbols,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                config_params=config_params
            )
            trace_ui(
                step="service_run_pipeline_done",
                run_id=run_name,
                strategy_id=strategy,
                file=__file__,
                func="_run_pipeline",
                extra={
                    "job_id": job_id,
                    "status": result.get("status"),
                    "run_name": run_name,
                    "strategy": strategy,
                    "symbols": symbols,
                    "timeframe": timeframe,
                    "start_date": start_date,
                    "end_date": end_date,
                    "config_params": config_params,
                },
            )

            # Handle results from new pipeline adapter (Phase 1-5)
            if result.get("status") == "failed_precondition":
                # NOT an error - gates blocked execution (expected)
                reason = result.get("reason", "unknown")
                details = result.get("details", "")

                with self._lock:
                    job_data = self.running_jobs.pop(job_id, {})
                    self.completed_jobs[job_id] = {
                        **job_data,
                        "status": "failed_precondition",
                        "reason": reason,
                        "details": details,
                        "ended_at": datetime.now().isoformat(),
                        "progress": f"Gates blocked: {reason}",
                    }
                return

            elif result.get("status") == "error":
                # Deterministic error with error_id
                error_id = result.get("error_id", "UNKNOWN")
                details = result.get("details", "")

                with self._lock:
                    job_data = self.running_jobs.pop(job_id, {})
                    self.completed_jobs[job_id] = {
                        **job_data,
                        "status": "error",
                        "error_id": error_id,
                        "details": details,
                        "ended_at": datetime.now().isoformat(),
                        "progress": f"Error (ID: {error_id})",
                    }
                return

            # Legacy adapter result format is no longer supported.

            effective_run_name = result["run_name"]

            # Success
            with self._lock:
                job_data = self.running_jobs.pop(job_id, {})
                self.completed_jobs[job_id] = {
                    **job_data,
                    "status": "completed",
                    "run_name": effective_run_name,
                    "ended_at": datetime.now().isoformat(),
                    "progress": "Backtest completed successfully",
                }

        except Exception as e:
            # Error - capture full traceback
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            full_traceback = traceback.format_exc()

            # Log to console for debugging
            print(f"\n{'='*60}")
            print(f"BACKTEST ERROR - Job ID: {job_id}")
            print(f"{'='*60}")
            print(full_traceback)
            print(f"{'='*60}\n")

            with self._lock:
                job_data = self.running_jobs.pop(job_id, {})
                self.completed_jobs[job_id] = {
                    **job_data,
                    "status": "failed",
                    "error": error_msg,
                    "traceback": full_traceback,  # Store full traceback
                    "ended_at": datetime.now().isoformat(),
                    "progress": f"Error: {error_msg}",
                }

    def _update_job_progress(self, job_id: str, progress: str):
        """Update progress message for a running job."""
        with self._lock:
            if job_id in self.running_jobs:
                self.running_jobs[job_id]["progress"] = progress

    def get_job_status(self, job_id: str) -> Dict:
        """Get current status of a backtest job.

        Args:
            job_id: Job identifier

        Returns:
            Job status dictionary with keys: status, progress, etc.
        """
        with self._lock:
            if job_id in self.running_jobs:
                return dict(self.running_jobs[job_id])
            elif job_id in self.completed_jobs:
                return dict(self.completed_jobs[job_id])
            return {"status": "not_found"}

    def get_all_jobs(self) -> Dict[str, Dict]:
        """Get status of all jobs (running + completed).

        Returns:
            Dictionary mapping job_id to job status
        """
        with self._lock:
            all_jobs = {}
            all_jobs.update(self.running_jobs)
            all_jobs.update(self.completed_jobs)
            return all_jobs

    def clear_completed_jobs(self):
        """Clear completed jobs from memory."""
        with self._lock:
            self.completed_jobs.clear()


# Global singleton instance
_backtest_service: Optional[BacktestService] = None


def get_backtest_service() -> BacktestService:
    """Get the global BacktestService instance (singleton pattern).

    Returns:
        BacktestService instance
    """
    global _backtest_service
    if _backtest_service is None:
        _backtest_service = BacktestService()
    return _backtest_service
