"""
Chart Logging Utilities
========================

Centralized logging infrastructure for chart callbacks.

Provides:
- Structured chart_meta logging (JSON single-line)
- Error ID generation and correlation
- Consistent logging across all chart types
"""

import uuid
import logging
import json
from typing import Any, Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)


def generate_error_id() -> str:
    """
    Generate a short, unique error ID for exception tracking.
    
    Returns:
        8-character uppercase hex string (e.g., "A1B2C3D4")
    """
    return uuid.uuid4().hex[:8].upper()


def build_chart_meta(
    source: str,
    symbol: str,
    timeframe: str,
    requested_date: Optional[str],
    effective_date: Optional[str],
    window_mode: Optional[str],
    rows_before: int,
    rows_after: int,
    dropped_rows: int,
    date_filter_mode: str,
    min_ts: Optional[pd.Timestamp],
    max_ts: Optional[pd.Timestamp],
    market_tz: str,
    display_tz: str,
    session_flags: Dict[str, bool],
    data_path: str,
) -> Dict[str, Any]:
    """
    Build structured chart metadata dict.
    
    All chart callbacks should use this to ensure consistent logging.
    
    Args:
        source: Data source (e.g., "BACKTEST_PARQUET", "LIVE_SQLITE")
        symbol: Stock symbol
        timeframe: Timeframe (M1/M5/M15/H1/D1)
        requested_date: Date from picker (may be None)
        effective_date: Actual date used after clamping/rollback
        window_mode: Window setting for D1 (1M/3M/6M/12M/All)
        rows_before: Total rows before filtering
        rows_after: Rows after all filtering
        dropped_rows: Rows removed by filters
        date_filter_mode: D1_WINDOW, INTRADAY_EXACT_DAY, or NONE
        min_ts: Earliest timestamp in final data
        max_ts: Latest timestamp in final data
        market_tz: Market timezone (always America/New_York for US stocks)
        display_tz: Display timezone from UI toggle
        session_flags: Dict of session toggle states (pre, after, etc.)
        data_path: Resolved file path(s) used
    
    Returns:
        Dict with all chart metadata (JSON-serializable)
    """
    return {
        "source": source,
        "symbol": symbol,
        "timeframe": timeframe,
        "requested_date": requested_date,
        "effective_date": effective_date,
        "window_mode": window_mode,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "dropped_rows": dropped_rows,
        "date_filter_mode": date_filter_mode,
        "min_ts": min_ts.isoformat() if min_ts else None,
        "max_ts": max_ts.isoformat() if max_ts else None,
        "market_tz": market_tz,
        "display_tz": display_tz,
        "session_flags": session_flags,
        "data_path": data_path,
    }


def log_chart_meta(chart_meta: Dict[str, Any]) -> None:
    """
    Log chart metadata as single-line JSON.
    
    Args:
        chart_meta: Dict from build_chart_meta()
    """
    logger.info(f"chart_meta {json.dumps(chart_meta)}")


def log_chart_error(
    error_id: str,
    exception: Exception,
    chart_meta: Dict[str, Any],
) -> None:
    """
    Log chart error with full stacktrace and correlation ID.
    
    This logs to errors.log with:
    - error_id for correlation
    - full exception details
    - chart_meta context
    
    Args:
        error_id: Generated error ID (from generate_error_id())
        exception: The exception that occurred
        chart_meta: Chart metadata dict for context
    """
    error_logger = logging.getLogger("errors")
    
    error_logger.error(
        f"Chart Error [error_id={error_id}]\n"
        f"Exception: {type(exception).__name__}: {str(exception)}\n"
        f"Context: {json.dumps(chart_meta, indent=2)}",
        exc_info=True
    )
