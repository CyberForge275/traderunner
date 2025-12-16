"""
Minimal Pipeline Example with Coverage Gate Integration

This module demonstrates how to integrate the coverage gate into
a backtest pipeline with proper artifact creation.

PATTERN:
1. create_run_dir() FIRST
2. write_run_meta() BEFORE execution
3. Coverage Gate → FAILED_PRECONDITION if gap
4. Execution (only if gates pass)
5. write_run_result() ALWAYS (in finally)
6. write_error_stacktrace() only on ERROR
"""

import logging
from datetime import datetime
from pathlib import Path
import pandas as pd

from backtest.services.data_coverage import check_coverage, CoverageStatus
from backtest.services.run_status import RunResult, RunStatus, FailureReason
from backtest.services.artifacts_manager import ArtifactsManager

logger = logging.getLogger(__name__)


def minimal_backtest_with_gates(
    run_id: str,
    symbol: str,
    timeframe: str,
    requested_end: str,
    lookback_days: int,
    strategy_params: dict,
    artifacts_root: Path = None
) -> RunResult:
    """
    Minimal backtest pipeline with coverage gate integration.
    
    Demonstrates:
    - Fail-safe artifact creation
    - Coverage gate as hard precondition
    - RunResult status propagation
    - UI-ready error messages
    
    Args:
        run_id: Unique run identifier
        symbol: Stock symbol
        timeframe: M1/M5/M15
        requested_end: End date ISO format
        lookback_days: Lookback in calendar days
        strategy_params: Strategy parameters
        artifacts_root: Artifacts directory (optional)
    
    Returns:
        RunResult with status (SUCCESS/FAILED_PRECONDITION/ERROR)
    """
    # Initialize artifacts manager
    manager = ArtifactsManager(artifacts_root=artifacts_root)
    
    # CRITICAL: Create run directory FIRST (even before any checks)
    try:
        manager.create_run_dir(run_id)
        logger.info(f"[{run_id}] Run directory created")
    except Exception as e:
        # Very rare - only if filesystem issues
        logger.error(f"[{run_id}] Failed to create run dir: {e}")
        return RunResult(
            run_id=run_id,
            status=RunStatus.ERROR,
            error_id="ARTIFACTS_CREATE_FAILED",
            details={"error": str(e)}
        )
    
    try:
        # Write run_meta.json at START (before execution)
        manager.write_run_meta(
            strategy="inside_bar",  # Example
            symbols=[symbol],
            timeframe=timeframe,
            params=strategy_params,
            requested_end=requested_end,
            lookback_days=lookback_days,
            commit_hash="abc123"  # Would be from git
        )
        logger.info(f"[{run_id}] run_meta.json written")
        
        # ===== PHASE 1: COVERAGE GATE =====
        logger.info(f"[{run_id}] Running coverage gate...")
        requested_end_ts = pd.Timestamp(requested_end, tz="America/New_York")
        
        coverage_result = check_coverage(
            symbol=symbol,
            timeframe=timeframe,
            requested_end=requested_end_ts,
            lookback_days=lookback_days,
            auto_fetch=False  # Fail-fast by default
        )
        
        # Write coverage check result (audit trail)
        manager.write_coverage_check_result(coverage_result)
        
        # Update manifest with coverage result
        if hasattr(manager, 'manifest_writer') and manager.manifest_writer:
            manager.manifest_writer.update_coverage_gate(coverage_result)
        
        # Check coverage status
        if coverage_result.status == CoverageStatus.GAP_DETECTED:
            logger.warning(f"[{run_id}] Coverage gap detected: {coverage_result.gap}")
            
            # Return FAILED_PRECONDITION (not ERROR)
            run_result = RunResult(
                run_id=run_id,
                status=RunStatus.FAILED_PRECONDITION,
                reason=FailureReason.DATA_COVERAGE_GAP,
                details=coverage_result.to_dict()
            )
            
            # Write run_result.json
            manager.write_run_result(run_result)
            
            return run_result
        
        elif coverage_result.status == CoverageStatus.FETCH_FAILED:
            logger.error(f"[{run_id}] Data fetch failed: {coverage_result.error_message}")
            
            # Also FAILED_PRECONDITION (data unavailable)
            run_result = RunResult(
                run_id=run_id,
                status=RunStatus.FAILED_PRECONDITION,
                reason=FailureReason.DATA_COVERAGE_GAP,
                details=coverage_result.to_dict()
            )
            
            manager.write_run_result(run_result)
            return run_result
        
        # Coverage SUFFICIENT → continue
        logger.info(f"[{run_id}] Coverage sufficient")
        
        # ===== PHASE 2: SLA GATE (Phase 3) =====
        # (Will be implemented in next commit)
        # sla_result = check_data_sla(df, strategy_key, timeframe, lookback_bars)
        # if not sla_result.passed: return FAILED_PRECONDITION(DATA_SLA_FAILED)
        
        # ===== PHASE 3: STRATEGY EXECUTION =====
        logger.info(f"[{run_id}] Executing strategy...")
        
        # TODO: Actual strategy execution
        # signals = run_strategy(...)
        
        # Simulate success
        logger.info(f"[{run_id}] Strategy execution complete")
        
        # SUCCESS
        run_result = RunResult(
            run_id=run_id,
            status=RunStatus.SUCCESS,
            details={
                "signals_count": 42,  # Example
                "coverage": coverage_result.to_dict()
            }
        )
        
        manager.write_run_result(run_result)
        logger.info(f"[{run_id}] Backtest complete: SUCCESS")
        
        return run_result
    
    except Exception as e:
        # Unhandled exception → ERROR
        logger.error(f"[{run_id}] Pipeline exception: {e}", exc_info=True)
        
        # Generate error_id for correlation
        error_id = _generate_error_id()
        
        run_result = RunResult(
            run_id=run_id,
            status=RunStatus.ERROR,
            error_id=error_id,
            details={
                "exception": str(e),
                "exception_type": type(e).__name__
            }
        )
        
        # Write run_result.json + error_stacktrace.txt
        manager.write_run_result(run_result)
        manager.write_error_stacktrace(e, error_id)
        
        logger.error(f"[{run_id}] Backtest failed: ERROR (error_id={error_id})")
        
        return run_result


def _generate_error_id() -> str:
    """Generate unique error ID for correlation."""
    import secrets
    return secrets.token_hex(6).upper()


# Example usage (for tests/integration)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    result = minimal_backtest_with_gates(
        run_id="test_integration_001",
        symbol="HOOD",
        timeframe="M15",
        requested_end="2025-12-12",
        lookback_days=100,
        strategy_params={"atr_period": 14},
        artifacts_root=Path("artifacts/backtests")
    )
    
    print(f"\nResult: {result.status.value}")
    if result.reason:
        print(f"Reason: {result.reason.value}")
    if result.error_id:
        print(f"Error ID: {result.error_id}")
