"""
Data quality validators and SLA enforcement.

Implements the SLAs defined in v2 architecture:
- m5_completeness >= 0.99
- lateness_minutes <= 5
- no_nan_ohlc
- no_dupe_index
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass


@dataclass
class SLAResult:
    """Result of an SLA check."""
    sla_name: str
    passed: bool
    measured_value: float
    threshold: float
    message: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            'sla_name': self.sla_name,
            'passed': bool(self.passed),
            'measured_value': float(self.measured_value),
            'threshold': float(self.threshold),
            'message': str(self.message),
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class DataQualitySLA:
    """
    Data quality SLA checker.
    
    Enforces v2 architecture SLAs:
    - M5 completeness >= 99%
    - Data lateness <= 5 minutes
    - No NaNs in OHLC
    - No duplicate timestamps
    """
    
    # SLA Thresholds
    MIN_M5_COMPLETENESS = 0.99  # 99%
    MAX_LATENESS_MINUTES = 5
    
    @classmethod
    def check_m5_completeness(
        cls, 
        df: pd.DataFrame,
        calendar=None
    ) -> SLAResult:
        """
        Check M5 data completeness within trading sessions.
        
        Expected: One bar every 5 minutes during market hours.
        """
        if len(df) == 0:
            return SLAResult(
                sla_name='m5_completeness',
                passed=False,
                measured_value=0.0,
                threshold=cls.MIN_M5_COMPLETENESS,
                message='Empty DataFrame'
            )
        
        # Calculate expected vs actual bars
        # TODO: Use calendar for precise session bounds
        start = df.index[0]
        end = df.index[-1]
        
        # Simple approximation: 6.5 hours/day * 12 bars/hour = 78 bars/day
        # For accurate check, need market calendar
        business_days = pd.bdate_range(start, end).size
        expected_bars = business_days * 78  # Approximate
        actual_bars = len(df)
        
        if expected_bars > 0:
            completeness = actual_bars / expected_bars
        else:
            completeness = 1.0
        
        passed = completeness >= cls.MIN_M5_COMPLETENESS
        
        return SLAResult(
            sla_name='m5_completeness',
            passed=passed,
            measured_value=completeness,
            threshold=cls.MIN_M5_COMPLETENESS,
            message=f"Completeness: {completeness:.2%} (expected ~{expected_bars} bars, got {actual_bars})"
        )
    
    @classmethod
    def check_no_nan_ohlc(cls, df: pd.DataFrame) -> SLAResult:
        """Check for NaNs in OHLC columns."""
        ohlc_cols = ['Open', 'High', 'Low', 'Close']
        available_cols = [col for col in ohlc_cols if col in df.columns]
        
        if not available_cols:
            return SLAResult(
                sla_name='no_nan_ohlc',
                passed=False,
                measured_value=0.0,
                threshold=0.0,
                message='OHLC columns not found'
            )
        
        nan_count = df[available_cols].isna().sum().sum()
        total_values = len(df) * len(available_cols)
        nan_ratio = nan_count / total_values if total_values > 0 else 0.0
        
        passed = nan_count == 0
        
        return SLAResult(
            sla_name='no_nan_ohlc',
            passed=passed,
            measured_value=nan_count,
            threshold=0.0,
            message=f"Found {nan_count} NaNs in OHLC ({nan_ratio:.2%})"
        )
    
    @classmethod
    def check_no_duplicates(cls, df: pd.DataFrame) -> SLAResult:
        """Check for duplicate index timestamps."""
        dup_count = df.index.duplicated().sum()
        
        passed = dup_count == 0
        
        return SLAResult(
            sla_name='no_dupe_index',
            passed=passed,
            measured_value=dup_count,
            threshold=0.0,
            message=f"Found {dup_count} duplicate timestamps"
        )
    
    @classmethod
    def check_lateness(
        cls, 
        df: pd.DataFrame,
        reference_time: Optional[datetime] = None
    ) -> SLAResult:
        """
        Check data lateness (how old is the latest data).
        
        Only relevant for real-time data.
        """
        if reference_time is None:
            reference_time = datetime.utcnow()
        
        if len(df) == 0:
            return SLAResult(
                sla_name='lateness',
                passed=False,
                measured_value=float('inf'),
                threshold=cls.MAX_LATENESS_MINUTES,
                message='Empty DataFrame'
            )
        
        latest_bar = df.index[-1]
        if latest_bar.tzinfo is None:
            latest_bar = latest_bar.tz_localize('UTC')
        
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=latest_bar.tzinfo)
        
        lateness = (reference_time - latest_bar).total_seconds() / 60.0  # minutes
        
        passed = lateness <= cls.MAX_LATENESS_MINUTES
        
        return SLAResult(
            sla_name='lateness',
            passed=passed,
            measured_value=lateness,
            threshold=cls.MAX_LATENESS_MINUTES,
            message=f"Data is {lateness:.1f} minutes old"
        )
    
    @classmethod
    def check_all(
        cls,
        df: pd.DataFrame,
        calendar=None,
        reference_time: Optional[datetime] = None,
        skip_lateness: bool = True  # Only for real-time
    ) -> Dict[str, SLAResult]:
        """
        Run all SLA checks.
        
        Returns dict of {sla_name: SLAResult}
        """
        results = {}
        
        results['m5_completeness'] = cls.check_m5_completeness(df, calendar)
        results['no_nan_ohlc'] = cls.check_no_nan_ohlc(df)
        results['no_dupe_index'] = cls.check_no_duplicates(df)
        
        if not skip_lateness:
            results['lateness'] = cls.check_lateness(df, reference_time)
        
        return results
    
    @classmethod
    def all_passed(cls, results: Dict[str, SLAResult]) -> bool:
        """Check if all SLAs passed."""
        return all(r.passed for r in results.values())


def validate_ohlcv_dataframe(
    df: pd.DataFrame,
    enforce_sla: bool = False,
    calendar=None
) -> tuple[bool, List[str]]:
    """
    Validate OHLCV DataFrame with optional SLA enforcement.
    
    Args:
        df: DataFrame to validate
        enforce_sla: If True, enforce SLAs (fail if SLA violations)
        calendar: Market calendar for session validation
        
    Returns:
        (is_valid, messages) tuple
    """
    from axiom_bt.contracts.data_contracts import DailyFrameSpec
    
    messages = []
    
    # Basic contract validation
    is_valid, violations = DailyFrameSpec.validate(df, strict=False)
    if not is_valid:
        messages.extend(violations)
    
    # SLA checks
    if enforce_sla:
        sla_results = DataQualitySLA.check_all(df, calendar=calendar)
        for sla_name, result in sla_results.items():
            if not result.passed:
                messages.append(f"SLA violation [{sla_name}]: {result.message}")
                is_valid = False
    
    return is_valid, messages


def validate_m5_completeness(
    df: pd.DataFrame,
    min_completeness: float = 0.99
) -> bool:
    """
    Quick check for M5 data completeness.
    
    Returns True if completeness >= min_completeness.
    """
    result = DataQualitySLA.check_m5_completeness(df)
    return result.measured_value >= min_completeness
