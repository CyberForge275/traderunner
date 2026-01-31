"""New Modular Pipeline Adapter - CORRECT SSOT Implementation.

This adapter uses axiom_bt.pipeline.runner.run_pipeline as the sole pipeline entry point.

Pipeline stages (modular architecture):
1. Data fetching with warmup calculation (data_fetcher.py)
2. Signal generation via intent (signals.py)
3. Fill model execution (fill_model.py)
4. Trade execution with compound sizing (execution.py)
5. Metrics computation (metrics.py)
6. Artifact generation (artifacts.py)
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


class NewPipelineAdapter:
    """
    Adapter for NEW MODULAR PIPELINE (CORRECT SSOT).

    Uses axiom_bt.pipeline.runner.run_pipeline which orchestrates:
    - Data fetching with automatic warmup
    - Signal generation (intent frame)
    - Fill model
    - Execution with compound sizing support
    - Metrics computation
    - Complete artifact generation
    
    The pipeline returns void and writes all artifacts directly to out_dir.
    """

    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """Initialize adapter with optional progress callback."""
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
        Execute backtest using new modular pipeline.

        Args:
            run_name: Unique run identifier
            strategy: Strategy name (e.g., "insidebar_intraday")
            symbols: List of symbols (currently supports single symbol)
            timeframe: Timeframe (M5, M15, H1, D1)
            start_date: Start date ISO format (YYYY-MM-DD)
            end_date: End date ISO format (YYYY-MM-DD)
            config_params: Strategy configuration parameters

        Returns:
            Dict with keys:
            - status: "success" | "failed"
            - run_name: Run directory name
            - run_dir: Absolute path to artifacts directory
            - error: Error message if failed (optional)
            - traceback: Full stacktrace if failed (optional)
        """
        try:
            self.progress_callback("🚀 Initializing modular pipeline...")

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
            from axiom_bt.utils.trace import trace_ui
            trace_ui(
                step="adapter_execute_backtest_start",
                run_id=run_name,
                strategy_id=strategy,
                strategy_version=strategy_params.get("strategy_version"),
                file=__file__,
                func="execute_backtest",
            )

            # Calculate lookback from date range
            from datetime import datetime, date

            lookback_days = 30  # Default
            if start_date and end_date:
                start = datetime.fromisoformat(start_date)
                end = datetime.fromisoformat(end_date)
                lookback_days = max((end - start).days, 1)

            requested_end = end_date if end_date else date.today().isoformat()

            self.progress_callback(f"📊 Running pipeline for {symbol} ({lookback_days}d)...")

            # Create run directory
            run_dir = Path("artifacts/backtests") / run_name
            run_dir.mkdir(parents=True, exist_ok=True)

            # Extract compound config from strategy_params
            backtesting_config = strategy_params.get("backtesting", {})
            compound_enabled = backtesting_config.get("compound_sizing", False)
            compound_equity_basis = backtesting_config.get("compound_equity_basis", "cash_only")

            # Extract strategy version
            strategy_version = strategy_params.get("strategy_version", "1.0.0")
            
            # Prepare bars_path (will be created by data_fetcher)
            bars_snapshot_path = run_dir / "bars_snapshot.parquet"
            
            # CRITICAL: Pipeline expects requested_end and lookback_days in strategy_params!
            # Also needs symbol and timeframe for data fetching
            strategy_params_with_meta = {
                **strategy_params,
                "requested_end": requested_end,
                "lookback_days": lookback_days,
                "symbol": symbol,
                "timeframe": timeframe,
            }
            
            # Extract core and tunable for SSOT structure
            # Pipeline expects strategy_meta with "core" and "tunable" sections
            core_keys = ["atr_period", "risk_reward_ratio", "min_mother_bar_size", 
                        "breakout_confirmation", "inside_bar_mode", "session_timezone",
                        "session_mode", "session_filter", "timeframe_minutes",
                        "valid_from_policy", "order_validity_policy"]
            tunable_keys = ["lookback_candles", "max_pattern_age_candles", 
                           "max_deviation_atr", "max_position_loss_pct_equity"]
            
            core_config = {k: strategy_params[k] for k in core_keys if k in strategy_params}
            tunable_config = {k: strategy_params[k] for k in tunable_keys if k in strategy_params}
            
            self.progress_callback("⚙️ Executing modular pipeline stages...")
            
            # Call NEW MODULAR PIPELINE (CORRECT!)
            # This function returns void - writes all artifacts directly
            trace_ui(
                step="adapter_call_run_pipeline",
                run_id=run_name,
                strategy_id=strategy,
                strategy_version=strategy_version,
                file=__file__,
                func="execute_backtest",
            )
            run_pipeline(
                run_id=run_name,
                out_dir=run_dir,
                bars_path=bars_snapshot_path,
                strategy_id=strategy,  # Use strategy name from UI
                strategy_version=strategy_version,
                strategy_params=strategy_params_with_meta,  # Includes requested_end, lookback_days, symbol, timeframe
                strategy_meta={
                    "core": core_config,
                    "tunable": tunable_config,
                    "required_warmup_bars": strategy_params.get("required_warmup_bars", 0),
                },
                compound_enabled=compound_enabled,
                compound_equity_basis=compound_equity_basis,
                initial_cash=DEFAULT_INITIAL_CASH,
                fees_bps=DEFAULT_FEE_BPS,
                slippage_bps=DEFAULT_SLIPPAGE_BPS,
            )



            # If we reach here, pipeline succeeded (would raise PipelineError otherwise)
            self.progress_callback("✅ Pipeline completed successfully!")
            trace_ui(
                step="adapter_run_pipeline_done",
                run_id=run_name,
                strategy_id=strategy,
                strategy_version=strategy_version,
                file=__file__,
                func="execute_backtest",
            )
            
            return {
                "status": "success",
                "run_name": run_name,
                "run_dir": str(run_dir),
            }

        except PipelineError as e:
            # Pipeline-specific error (data fetching, warmup, signals, execution, etc.)
            import traceback
            import logging
            
            logger = logging.getLogger(__name__)
            error_msg = str(e)
            full_traceback = traceback.format_exc()
            
            logger.error(
                f"❌ Pipeline error:\n"
                f"  Run: {run_name}\n"
                f"  Error: {error_msg}\n"
                f"  Traceback:\n{full_traceback}"
            )
            
            self.progress_callback(f"❌ Pipeline failed: {error_msg}")
            
            # Ensure run_dir exists
            run_dir = Path("artifacts/backtests") / run_name
            run_dir.mkdir(parents=True, exist_ok=True)
            
            # Write error stacktrace
            error_trace_path = run_dir / "error_stacktrace.txt"
            try:
                with open(error_trace_path, 'w') as f:
                    f.write(f"Pipeline Error\n")
                    f.write(f"{'='*60}\n\n")
                    f.write(f"Run ID: {run_name}\n")
                    f.write(f"Error: {error_msg}\n\n")
                    f.write(f"Stacktrace:\n")
                    f.write(full_traceback)
                logger.info(f"✅ Wrote error_stacktrace.txt to {error_trace_path}")
            except Exception as write_err:
                logger.error(f"❌ Could not write error stacktrace: {write_err}")
            
            return {
                "status": "failed",
                "error": error_msg,
                "traceback": full_traceback,
                "run_name": run_name,
                "run_dir": str(run_dir),
            }

        except Exception as e:
            # CRITICAL: Catch ALL exceptions (not just PipelineError)
            # This prevents silent thread deaths in Dashboard context
            import traceback
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Log the full exception with traceback
            error_type = type(e).__name__
            error_msg = str(e)
            full_traceback = traceback.format_exc()
            
            logger.error(
                f"❌ Pipeline adapter exception:\n"
                f"  Run: {run_name}\n"
                f"  Type: {error_type}\n"
                f"  Message: {error_msg}\n"
                f"  Traceback:\n{full_traceback}"
            )
            
            # Update progress callback with error
            self.progress_callback(f"❌ Pipeline failed: {error_type}: {error_msg}")
            
            # Ensure run_dir exists even if pipeline failed early
            run_dir = Path("artifacts/backtests") / run_name
            run_dir.mkdir(parents=True, exist_ok=True)
            
            # Write error stacktrace for debugging
            error_trace_path = run_dir / "error_stacktrace.txt"
            try:
                with open(error_trace_path, 'w') as f:
                    f.write(f"Adapter Exception\n")
                    f.write(f"{'='*60}\n\n")
                    f.write(f"Run ID: {run_name}\n")
                    f.write(f"Exception Type: {error_type}\n")
                    f.write(f"Exception Message: {error_msg}\n\n")
                    f.write(f"Stacktrace:\n")
                    f.write(full_traceback)
                logger.info(f"✅ Wrote error_stacktrace.txt to {error_trace_path}")
            except Exception as trace_err:
                logger.error(f"❌ Could not write error_stacktrace.txt: {trace_err}")
            
            # Return failure response to Dashboard
            return {
                "status": "failed",
                "error": f"{error_type}: {error_msg}",
                "traceback": full_traceback,
                "run_name": run_name,
                "run_dir": str(run_dir),
                "details": {
                    "exception_type": error_type,
                    "adapter": "new_pipeline_adapter",
                    "has_stacktrace_file": error_trace_path.exists()
                }
            }


def create_new_adapter(progress_callback: Optional[Callable[[str], None]] = None) -> NewPipelineAdapter:
    """
    Factory function for new pipeline adapter.
    
    Args:
        progress_callback: Optional callback for progress updates
        
    Returns:
        NewPipelineAdapter instance
    """
    return NewPipelineAdapter(progress_callback=progress_callback)
