"""New Pipeline Adapter - Uses the SSOT modular pipeline runner.

This adapter bypasses legacy runners and calls the pipeline orchestrator
directly. The engine layer is responsible for:

- Bars snapshot / data fetch
- Signal detection + orders generation
- Fills + execution + metrics
- Structured artifacts (run_meta/run_result/run_manifest)
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

from core.settings import DEFAULT_INITIAL_CASH, DEFAULT_FEE_BPS, DEFAULT_SLIPPAGE_BPS
from axiom_bt.pipeline.runner import run_pipeline, PipelineError
from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore


class NewPipelineAdapter:
    """Adapter for the SSOT modular pipeline runner."""

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
            self.progress_callback("Initializing pipeline backtest...")

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

            version = strategy_params.get("strategy_version", "1.0.0")
            defaults = StrategyConfigStore.get_defaults(strategy, version)
            strategy_meta = {
                "required_warmup_bars": defaults.get("required_warmup_bars", 0),
                "core": defaults.get("core", {}),
                "tunable": defaults.get("tunable", {}),
            }

            compound_cfg = strategy_params.get("backtesting", {}) or {}
            compound_enabled = bool(compound_cfg.get("compound_sizing", False))
            compound_equity_basis = compound_cfg.get("compound_equity_basis", "cash_only")

            pipeline_params = {
                **strategy_params,
                "symbol": symbol,
                "timeframe": timeframe,
                "requested_end": requested_end,
                "lookback_days": lookback_days,
            }

            session_mode = strategy_meta.get("core", {}).get("session_mode", "rth")
            bars_path = run_dir / "bars" / f"bars_exec_{timeframe}_{session_mode}.parquet"

            run_pipeline(
                run_id=run_name,
                out_dir=run_dir,
                bars_path=bars_path,
                strategy_id=strategy,
                strategy_version=version,
                strategy_params=pipeline_params,
                strategy_meta=strategy_meta,
                compound_enabled=compound_enabled,
                compound_equity_basis=compound_equity_basis,
                initial_cash=DEFAULT_INITIAL_CASH,
                fees_bps=DEFAULT_FEE_BPS,
                slippage_bps=DEFAULT_SLIPPAGE_BPS,
            )

            self.progress_callback("Pipeline backtest completed successfully!")
            return {
                "status": "success",
                "run_name": run_name,
                "run_dir": str(run_dir),
                "result": None,
            }

        except PipelineError as e:
            return {
                "status": "error",
                "error_id": "PIPELINE_ERROR",
                "details": str(e),
                "run_name": run_name,
            }
        except Exception as e:
            # Unexpected exception (outside pipeline)
            import traceback
            return {
                "status": "error",
                "error_id": "PIPELINE_EXCEPTION",
                "details": f"{type(e).__name__}: {str(e)}",
                "traceback": traceback.format_exc(),
                "run_name": run_name,
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
