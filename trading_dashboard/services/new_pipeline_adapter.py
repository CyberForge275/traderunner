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
import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable

# Add traderunner src to path
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
# NOTE: this module lives in trading_dashboard/services/, so repo root is parents[2].
REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_CONFIG = REPO_ROOT / "configs" / "runs" / "backtest_pipeline_defaults.yaml"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.settings import DEFAULT_INITIAL_CASH
from core.settings.runtime_config import get_marketdata_data_root
from axiom_bt.pipeline.marketdata_stream_client import (
    MarketdataStreamClient,
    build_ensure_request_for_pipeline,
)
from axiom_bt.pipeline.runner import run_pipeline, PipelineError
from axiom_bt.pipeline.paths import get_artifacts_root, get_backtest_run_dir
from axiom_bt.pipeline.data_fetcher import MissingHistoricalDataError as PipelineMissingHistoricalDataError
from trading_dashboard.services.errors import MissingHistoricalDataError

logger = logging.getLogger(__name__)


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
        # UI/Spyder parity for multi-symbol behavior: run once per symbol.
        if isinstance(symbols, (list, tuple)) and len(symbols) > 1:
            import copy

            last_result = None
            for sym in symbols:
                nested_run_name = f"{run_name}__{sym}" if run_name else run_name
                last_result = self.execute_backtest(
                    run_name=nested_run_name,
                    strategy=strategy,
                    symbols=[sym],
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    config_params=copy.deepcopy(config_params or {}),
                )
            return last_result

        try:
            self.progress_callback("🚀 Initializing modular pipeline...")

            # Validate inputs
            if not symbols or len(symbols) == 0:
                run_dir = get_backtest_run_dir(run_name)
                return {
                    "status": "failed",
                    "error": "No symbols provided",
                    "run_name": run_name,
                    "run_dir": str(run_dir)
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

            from datetime import date, datetime
            lookback_days = strategy_params.get("lookback_days")
            if lookback_days is not None:
                lookback_days = max(int(lookback_days), 1)
            else:
                lookback_days = 30
                if start_date and end_date:
                    start = datetime.fromisoformat(start_date)
                    end = datetime.fromisoformat(end_date)
                    lookback_days = max((end - start).days, 1)

            requested_end = end_date if end_date else date.today().isoformat()

            self.progress_callback(f"📊 Running pipeline for {symbol} ({lookback_days}d)...")

            # Resolve artifacts root once per run.
            run_dir = get_backtest_run_dir(run_name)
            logger.info(
                "actions: artifacts_root resolved_root=%s run=%s",
                get_artifacts_root(),
                run_name,
            )

            # Extract compound config from strategy_params
            backtesting_config = strategy_params.get("backtesting", {})
            compound_enabled = backtesting_config.get("compound_sizing", False)
            compound_equity_basis = backtesting_config.get("compound_equity_basis", "cash_only")

            # Extract strategy version
            strategy_version = strategy_params.get("strategy_version", "1.0.0")
            
            # Prepare bars_path (will be created by data_fetcher)
            bars_snapshot_path = run_dir / "bars_snapshot.parquet"

            consumer_only = os.getenv("PIPELINE_CONSUMER_ONLY", "0").strip().lower() in (
                "1",
                "true",
                "yes",
                "y",
                "on",
            )
            
            # CRITICAL: Pipeline expects requested_end and lookback_days in strategy_params!
            # Also needs symbol and timeframe for data fetching
            strategy_params_with_meta = {
                **strategy_params,
                "requested_end": requested_end,
                "lookback_days": lookback_days,
                "symbol": symbol,
                "timeframe": timeframe,
                "consumer_only": consumer_only,
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

            # Optional ensure/backfill via marketdata-service before pipeline run.
            marketdata_stream_url = os.getenv("MARKETDATA_STREAM_URL")
            ensure_req = None
            md_client = MarketdataStreamClient(base_url=marketdata_stream_url)
            if md_client.is_configured():
                timeframe_minutes = int(strategy_params.get("timeframe_minutes", 5))
                lookback_candles = int(strategy_params.get("lookback_candles", 0))
                session_mode = str(strategy_params.get("session_mode", "rth"))
                ensure_req = build_ensure_request_for_pipeline(
                    symbol=symbol,
                    timeframe_minutes=timeframe_minutes,
                    start_date=start_date or requested_end,
                    end_date=requested_end,
                    lookback_candles=lookback_candles,
                    session_timezone=str(strategy_params.get("session_timezone", "America/New_York")),
                    session_mode=session_mode,
                    session_filter=strategy_params.get("session_filter"),
                    data_root=str(get_marketdata_data_root()),
                )
                logger.info(
                    "actions: ensure_bars_request run=%s symbol=%s range=%s..%s url=%s",
                    run_name,
                    symbol,
                    ensure_req.start_date.isoformat(),
                    ensure_req.end_date.isoformat(),
                    md_client.base_url,
                )
                try:
                    ensure_res = md_client.ensure_bars(ensure_req)
                except Exception as ensure_err:
                    logger.exception(
                        "actions: ensure_bars_failed run=%s symbol=%s",
                        run_name,
                        symbol,
                    )
                    raise MissingHistoricalDataError(
                        symbol=symbol,
                        requested_range=f"{ensure_req.start_date}..{ensure_req.end_date}",
                        reason="ensure_bars_failed",
                        hint=f"marketdata-service /ensure_timeframe_bars failed: {ensure_err}",
                    ) from ensure_err
                logger.info(
                    "actions: ensure_bars_result run=%s symbol=%s status=%s gaps_before=%s gaps_after=%s",
                    run_name,
                    symbol,
                    ensure_res.get("status"),
                    len(ensure_res.get("gaps_before", []) or []),
                    len(ensure_res.get("gaps_after", []) or []),
                )
            
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
            attempted_recovery = False
            while True:
                try:
                    logger.info(
                        "actions: ui_backtest_range_resolved run=%s symbol=%s lookback_days=%s start=%s end=%s",
                        run_name,
                        symbol,
                        lookback_days,
                        start_date,
                        requested_end,
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
                        # Costs are resolved from YAML/overrides in pipeline resolver (SSOT).
                        fees_bps=0.0,
                        slippage_bps=0.0,
                        base_config_path=BASE_CONFIG if BASE_CONFIG.exists() else None,
                    )
                    break
                except PipelineError as run_err:
                    cause = run_err.__cause__
                    if (
                        not attempted_recovery
                        and isinstance(cause, PipelineMissingHistoricalDataError)
                        and ensure_req is not None
                    ):
                        try:
                            md_client = MarketdataStreamClient(base_url=marketdata_stream_url)
                            if md_client.is_configured():
                                logger.info(
                                    "actions: marketdata_stream_ensure_retry run=%s symbol=%s",
                                    run_name,
                                    symbol,
                                )
                                md_client.ensure_bars(ensure_req)
                                attempted_recovery = True
                                continue
                        except Exception as ensure_err:
                            logger.error(
                                "actions: marketdata_stream_ensure_retry_failed run=%s symbol=%s err=%s",
                                run_name,
                                symbol,
                                ensure_err,
                            )
                    raise



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
            error_msg = str(e)
            full_traceback = traceback.format_exc()
            
            logger.error(
                f"❌ Pipeline error:\n"
                f"  Run: {run_name}\n"
                f"  Error: {error_msg}\n"
                f"  Traceback:\n{full_traceback}"
            )
            if isinstance(e.__cause__, PipelineMissingHistoricalDataError):
                hint = (
                    "Backfill required (Option B): run marketdata-backfill CLI/service "
                    "and ensure data exists in MARKETDATA_DATA_ROOT."
                )
                logger.exception(
                    "actions: missing_historical_data run=%s symbol=%s range=%s hint=%s",
                    run_name,
                    symbol,
                    f"{start_date}..{end_date}",
                    hint,
                )
                raise MissingHistoricalDataError(
                    symbol=symbol,
                    requested_range=f"{start_date}..{end_date}",
                    reason="gap detected",
                    hint=hint,
                ) from e
            
            self.progress_callback(f"❌ Pipeline failed: {error_msg}")
            
            # Ensure run_dir exists
            run_dir = get_backtest_run_dir(run_name)
            
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
            run_dir = get_backtest_run_dir(run_name)
            
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
