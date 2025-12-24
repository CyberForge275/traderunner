"""
Postcondition Gates - Verify artifacts after backtest execution.

ARCHITECTURE:
- Defensive verification: Ensure expected artifacts exist for execution mode
- Clear failure messages for debugging
- Fail-safe: Missing artifacts → FAILED_POSTCONDITION (not silent success)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass
class EquityPostcondition:
    """Result of equity postcondition check."""
    status: Literal["pass", "fail"]
    equity_file_exists: bool
    equity_rows: int
    error_message: Optional[str]


def check_equity_postcondition(
    run_dir: Path,
    execution_mode: str
) -> EquityPostcondition:
    """
    Verify equity_curve.csv exists for full_backtest mode.
    
    Rule: If execution_mode=full_backtest, equity_curve.csv MUST exist
          (even if empty/flat - indicates 0 trades is valid)
    
    Args:
        run_dir: Run artifacts directory
        execution_mode: Execution mode from run_meta.json
    
    Returns:
        EquityPostcondition with pass/fail status
    """
    # Only check for full_backtest mode
    if execution_mode != "full_backtest":
        logger.debug(f"Skipping equity postcondition (mode={execution_mode})")
        return EquityPostcondition(
            status="pass",
            equity_file_exists=False,
            equity_rows=0,
            error_message=None
        )
    
    equity_path = run_dir / "equity_curve.csv"
    
    if not equity_path.exists():
        error_msg = (
            f"equity_curve.csv not found in {run_dir}. "
            f"Full backtest mode requires equity persistence."
        )
        logger.error(f"[{run_dir.name}] Postcondition FAILED: {error_msg}")
        return EquityPostcondition(
            status="fail",
            equity_file_exists=False,
            equity_rows=0,
            error_message=error_msg
        )
    
    # Verify file is readable (not corrupted)
    try:
        df = pd.read_csv(equity_path)
        rows = len(df)
        logger.info(f"[{run_dir.name}] Equity postcondition PASSED ({rows} rows)")
    except Exception as e:
        error_msg = f"equity_curve.csv exists but is unreadable: {e}"
        logger.error(f"[{run_dir.name}] Postcondition FAILED: {error_msg}")
        return EquityPostcondition(
            status="fail",
            equity_file_exists=True,
            equity_rows=0,
            error_message=error_msg
        )
    
    # Empty equity is OK (0 trades scenario)
    return EquityPostcondition(
        status="pass",
        equity_file_exists=True,
        equity_rows=rows,
        error_message=None
    )
