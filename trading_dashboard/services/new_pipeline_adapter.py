"""
New Pipeline Adapter - Uses Phase 1-5 Robust Pipeline

Bypasses legacy Streamlit code and calls minimal_backtest_with_gates() directly.
Produces proper SSOT artifacts: run_meta.json, run_result.json, run_manifest.json
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Callable

# Add traderunner src to path
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backtest.examples.minimal_pipeline import minimal_backtest_with_gates
from backtest.services.run_status import RunStatus, FailureReason


class NewPipelineAdapter:
    """
    Adapter for Phase 1-5 robust pipeline.
    
    Replaces legacy pipeline with minimal_backtest_with_gates() which enforces:
    - Coverage Gate (FAILED_PRECONDITION if gap)
    - SLA Gate (FAILED_PRECONDITION if violations)
    - Proper artifacts (run_meta/run_result/run_manifest)
    - No generic "Pipeline Exception"
    """
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        self.progress_callback = progress_callback or (lambda msg: None)
    
    def execute_backtest(
        self,
        run_name: str,
        strategy: str,
        symbols: List[str],
        timeframe: str,
        start_date: Optional[str],
        end_date: Optional[str],
        config_params: Optional[Dict] = None
    ) -> Dict:
        """
        Execute backtest using robust Phase 1-5 pipeline.
        
        Returns:
            Dict with keys:
            - status: "success" | "failed_precondition" | "error"
            - run_name: Actual run directory name (SSOT)
            - run_dir: Absolute path to artifacts directory (for UI binding)
            - reason: FailureReason if FAILED_PRECONDITION
            - error_id: Error ID if ERROR
            - details: Additional context
            - result: Full RunResult object
        """
        try:
            self.progress_callback("Initializing backtest...")
            
            # Validate inputs
            if not symbols or len(symbols) == 0:
                return {
                    "status": "failed",
                    "error": "No symbols provided",
                    "run_name": run_name,
                    "run_dir": f"artifacts/backtests/{run_name}"
                }
            
            symbol = symbols[0]  # minimal_pipeline takes single symbol
            
            # Parse config params
            strategy_params = config_params or {}
            
            # Calculate lookback from date range if provided
            lookback_days = 100  # Default
            if start_date and end_date:
                from datetime import datetime
                start = datetime.fromisoformat(start_date)
                end = datetime.fromisoformat(end_date)
                lookback_days = (end - start).days
            
            requested_end = end_date if end_date else None
            
            self.progress_callback(f"Running coverage & SLA gates for {symbol}...")
            
            # Determine run_dir (SSOT)
            run_dir = Path("artifacts/backtests") / run_name
            
            # Call Phase 1-5 pipeline
            result = minimal_backtest_with_gates(
                run_id=run_name,
                symbol=symbol,
                timeframe=timeframe,
                requested_end=requested_end,
                lookback_days=lookback_days,
                strategy_params=strategy_params,
                artifacts_root=Path("artifacts/backtests")
            )
            
            # Map RunResult to UI response format
            if result.status == RunStatus.SUCCESS:
                self.progress_callback("Backtest completed successfully!")
                return {
                    "status": "success",
                    "run_name": run_name,
                    "run_dir": str(run_dir),  # SSOT for UI
                    "result": result
                }
            
            elif result.status == RunStatus.FAILED_PRECONDITION:
                # This is NOT an error - it's a deterministic gate failure
                reason_str = result.reason.value if result.reason else "unknown"
                details_str = str(result.details) if result.details else "No details"
                
                self.progress_callback(f"Gates blocked execution: {reason_str}")
                
                return {
                    "status": "failed_precondition",
                    "reason": reason_str,
                    "details": details_str,
                    "run_name": run_name,
                    "run_dir": str(run_dir),  # SSOT for UI
                    "result": result
                }
            
            else:  # ERROR
                error_id = result.error_id or "UNKNOWN"
                
                self.progress_callback(f"Backtest error (ID: {error_id})")
                
                return {
                    "status": "error",
                    "error_id": error_id,
                    "details": result.details,
                    "run_name": run_name,
                    "result": result
                }
        
        except Exception as e:
            # Unexpected exception (outside pipeline)
            import traceback
            return {
                "status": "failed",
                "error": f"Pipeline exception: {type(e).__name__}: {str(e)}",
                "traceback": traceback.format_exc(),
                "run_name": run_name
            }


def create_new_adapter(progress_callback: Optional[Callable[[str], None]] = None) -> NewPipelineAdapter:
    """
    Factory function for new pipeline adapter.
    
    Args:
        progress_callback: Optional progress callback
    
    Returns:
        NewPipelineAdapter instance
    """
    return NewPipelineAdapter(progress_callback)
