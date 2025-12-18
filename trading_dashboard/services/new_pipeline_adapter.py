"""New Pipeline Adapter - Uses Phase 1-6 Robust FULL_BACKTEST pipeline.

This adapter bypasses the legacy Streamlit subprocess pipeline and calls
``run_backtest_full`` directly. The engine layer is responsible for:

- Coverage Gate (FAILED_PRECONDITION on gaps)
- Signal detection + orders generation (InsideBar via IntradayStore)
- Full trade simulation (ReplayEngine)
- Equity/orders/trades/metrics persistence
- Postcondition gate (FAILED_POSTCONDITION if equity missing)
- Structured artifacts (run_meta/run_result/run_manifest + artifacts_index.json)
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

from axiom_bt.full_backtest_runner import run_backtest_full
from backtest.services.run_status import RunStatus, FailureReason


class NewPipelineAdapter:
    """
    Adapter for FULL BACKTEST pipeline (SSOT).
    
    Calls run_backtest_full() which enforces:
    - Coverage Gate (FAILED_PRECONDITION if gap)
    - Full trade simulation (ReplayEngine)
    - Equity/orders/trades persistence
    - Postcondition gate (FAILED_POSTCONDITION if equity missing)
    - Proper artifacts (run_meta/run_result/run_manifest + artifacts_index.json)
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
        Execute FULL backtest using complete simulation pipeline.
        
        Returns:
            Dict with keys:
            - status: "success" | "failed_precondition" | "failed_postcondition" | "error"
            - run_name: Actual run directory name (SSOT)
            - run_dir: Absolute path to artifacts directory (for UI binding)
            - reason: FailureReason if FAILED_PRECONDITION/POSTCONDITION
            - error_id: Error ID if ERROR
            - details: Additional context
            - result: Full RunResult object
        """
        try:
            self.progress_callback("Initializing full backtest...")
            
            # Validate inputs
            if not symbols or len(symbols) == 0:
                return {
                    "status": "failed",
                    "error": "No symbols provided",
                    "run_name": run_name,
                    "run_dir": f"artifacts/backtests/{run_name}"
                }
            
            symbol = symbols[0]  # Single symbol for now
            
            # Parse config params
            strategy_params = config_params or {}

            # Calculate lookback from date range if provided
            from datetime import datetime, date

            lookback_days = 100  # Default
            if start_date and end_date:
                start = datetime.fromisoformat(start_date)
                end = datetime.fromisoformat(end_date)
                # Ensure we always have at least a 1-day lookback window
                lookback_days = max((end - start).days, 1)

            # requested_end is required by the coverage gate; default to
            # today's date if the UI did not provide an explicit end.
            requested_end = end_date if end_date else date.today().isoformat()
            
            self.progress_callback(f"Running full backtest for {symbol}...")
            
            # Determine run_dir (SSOT)
            run_dir = Path("artifacts/backtests") / run_name
            
            # Call FULL BACKTEST pipeline (SSOT)
            result = run_backtest_full(
                run_id=run_name,
                symbol=symbol,
                timeframe=timeframe,
                requested_end=requested_end,
                lookback_days=lookback_days,
                strategy_key="inside_bar",  # TODO: Map from strategy param
                strategy_params=strategy_params,
                artifacts_root=Path("artifacts/backtests"),
                market_tz="America/New_York",
                initial_cash=100000.0,
                costs={"fees_bps": 0.0, "slippage_bps": 0.0},
                debug_trace=bool(strategy_params.get("debug_trace", False)),
            )
            
            # Map RunResult to UI response format
            if result.status == RunStatus.SUCCESS:
                self.progress_callback("Full backtest completed successfully!")
                return {
                    "status": "success",
                    "run_name": run_name,
                    "run_dir": str(run_dir),  # SSOT for UI
                    "result": result
                }
            
            elif result.status == RunStatus.FAILED_PRECONDITION:
                # Precondition gate failure (coverage gap, SLA failure, etc.)
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
            
            elif result.status == RunStatus.FAILED_POSTCONDITION:
                # Postcondition gate failure (equity missing after full backtest)
                reason_str = result.reason.value if result.reason else "unknown"
                details_str = str(result.details) if result.details else "No details"
                
                self.progress_callback(f"Postcondition failed: {reason_str}")
                
                return {
                    "status": "failed_postcondition",
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
