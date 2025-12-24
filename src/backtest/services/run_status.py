"""
Run Status Model

Defines backtest run status and failure reasons.

ARCHITECTURE:
- Engine/Service layer (UI-independent)
- Immutable result DTOs
- Clear failure classification (no generic "error")
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any


class RunStatus(Enum):
    """Backtest run terminal status."""
    SUCCESS = "success"
    FAILED_PRECONDITION = "failed_precondition"
    FAILED_POSTCONDITION = "failed_postcondition"  # NEW: Postcondition gate failed
    ERROR = "error"


class FailureReason(Enum):
    """Specific failure reasons for FAILED_PRECONDITION/POSTCONDITION status."""
    DATA_COVERAGE_GAP = "data_coverage_gap"
    DATA_SLA_FAILED = "data_sla_failed"
    SCHEMA_MISSING = "schema_missing"
    EMPTY_DAY = "empty_day"
    TZ_ERROR = "tz_error"
    EQUITY_POSTCONDITION_FAILED = "equity_postcondition_failed"  # NEW: Equity missing after full backtest


@dataclass
class RunResult:
    """
    Immutable result of backtest run.
    
    Attributes:
        run_id: Unique run identifier
        status: Terminal status (SUCCESS / FAILED_PRECONDITION / ERROR)
        reason: Failure reason (only if FAILED_PRECONDITION)
        details: Additional context (dict)
        error_id: Error correlation ID (only if ERROR)
    """
    run_id: str
    status: RunStatus
    reason: Optional[FailureReason] = None
    details: Optional[Dict[str, Any]] = None
    error_id: Optional[str] = None
    
    def to_dict(self):
        """Convert to dict for serialization."""
        return {
            'run_id': self.run_id,
            'status': self.status.value,
            'reason': self.reason.value if self.reason else None,
            'details': self.details,
            'error_id': self.error_id
        }
