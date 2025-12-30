"""
Runtime History Status and DTOs

Defines the contract for ensure_history() and strategy execution gating.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List
import pandas as pd


class HistoryStatus(Enum):
    """
    Runtime history status.

    Strategy execution is ONLY allowed if status == SUFFICIENT.
    """
    SUFFICIENT = "sufficient"    # Ready for strategy execution
    LOADING = "loading"          # Backfilling in progress
    DEGRADED = "degraded"        # Cannot satisfy requirement


@dataclass
class DateRange:
    """Timestamp range for gaps."""
    start: pd.Timestamp
    end: pd.Timestamp

    def to_dict(self):
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat()
        }


@dataclass
class HistoryCheckResult:
    """
    Result of runtime history check.

    CRITICAL CONTRACT:
    - Strategy execution is ONLY allowed if status == SUFFICIENT
    - Otherwise: NO-SIGNALS with logged reason
    """
    status: HistoryStatus
    symbol: str
    tf: str
    base_tf_used: str  # For history calculation

    # Required window (from manifest params)
    required_start_ts: pd.Timestamp  # market_tz
    required_end_ts: pd.Timestamp    # market_tz

    # Cached window (from pre_paper_cache.db)
    cached_start_ts: Optional[pd.Timestamp]
    cached_end_ts: Optional[pd.Timestamp]

    # Gaps (if any)
    gaps: List[DateRange]

    # Backfill status
    fetch_attempted: bool
    fetch_success: bool

    # Degradation reason
    reason: Optional[str]

    def to_dict(self):
        return {
            "status": self.status.value,
            "symbol": self.symbol,
            "tf": self.tf,
            "base_tf_used": self.base_tf_used,
            "required_window": {
                "start": self.required_start_ts.isoformat(),
                "end": self.required_end_ts.isoformat()
            },
            "cached_window": {
                "start": self.cached_start_ts.isoformat() if self.cached_start_ts else None,
                "end": self.cached_end_ts.isoformat() if self.cached_end_ts else None
            },
            "gaps": [g.to_dict() for g in self.gaps],
            "fetch_attempted": self.fetch_attempted,
            "fetch_success": self.fetch_success,
            "reason": self.reason
        }
