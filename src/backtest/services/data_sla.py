"""
Data SLA Gate

Validates data quality before strategy execution.

CRITICAL FEATURES:
1. Gap-based completeness (not just ratio)
   - ANY missing bar in lookback window → FATAL for InsideBar
   - Consecutive bars required for pattern detection

2. Base TF awareness
   - m5_completeness only checked if M5 is base TF
   - M15 direct run: check M15 completeness (not M5)

3. Hard gate (not warning)
   - SLA failures → FAILED_PRECONDITION
   - Strategy execution blocked if SLAs fail

ARCHITECTURE:
- Engine/Service layer (UI-independent)
- Returns SLAResult DTO (never raises)
- Severity: FATAL vs WARNING
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class SLASeverity(Enum):
    """SLA violation severity."""
    FATAL = "fatal"
    WARNING = "warning"


@dataclass
class SLAViolation:
    """Single SLA violation details."""
    sla_name: str
    severity: SLASeverity
    measured_value: float
    threshold: float
    message: str


@dataclass
class SLAResult:
    """
    Result of SLA check.

    ALWAYS returned (never raises).
    """
    passed: bool
    violations: List[SLAViolation]
    base_timeframe: str  # M1, M5, M15 (for context)

    def fatal_violations(self) -> List[SLAViolation]:
        """Get only FATAL violations."""
        return [v for v in self.violations if v.severity == SLASeverity.FATAL]

    def to_dict(self):
        """Convert to dict for serialization."""
        return {
            'passed': self.passed,
            'violations': [
                {
                    'sla_name': v.sla_name,
                    'severity': v.severity.value,
                    'measured_value': v.measured_value,
                    'threshold': v.threshold,
                    'message': v.message
                }
                for v in self.violations
            ],
            'base_timeframe': self.base_timeframe
        }


def check_data_sla(
    df: pd.DataFrame,
    strategy_key: str,
    timeframe: str,  # M1/M5/M15 - the ACTUAL timeframe being used
    lookback_bars: int = 50  # For gap-based check
) -> SLAResult:
    """
    Check data SLAs before strategy execution.

    ⚠️ CRITICAL CHANGES:
    1. m5_completeness only checked if M5 is base TF
       - M15 run: M15 is base → no m5_completeness check
       - M5 run: M5 is base → check m5_completeness

    2. Completeness is GAP-BASED (not just ratio):
       - Check lookback window (e.g., last 50 bars for InsideBar)
       - ANY missing bar in window → FATAL
       - Ratio-based check is secondary (WARNING only)

    InsideBar REQUIRED SLAs:
    - no_nan_ohlc: FATAL (pattern detection needs clean OHLC)
    - completeness (gap-based): FATAL (consecutive bars required)

    Args:
        df: DataFrame with OHLC data (timezone-aware index)
        strategy_key: Strategy identifier (e.g., "inside_bar")
        timeframe: M1/M5/M15 (the base timeframe)
        lookback_bars: Number of bars to check for gaps

    Returns:
        SLAResult (always, never raises)
    """
    violations = []
    base_tf = timeframe

    # SLA 1: no_nan_ohlc (FATAL for all strategies)
    if 'open' not in df.columns or 'high' not in df.columns or \
       'low' not in df.columns or 'close' not in df.columns:
        violations.append(SLAViolation(
            sla_name='no_nan_ohlc',
            severity=SLASeverity.FATAL,
            measured_value=0.0,
            threshold=0.0,
            message="OHLC columns not found"
        ))
    else:
        nan_count = df[['open', 'high', 'low', 'close']].isnull().sum().sum()
        if nan_count > 0:
            violations.append(SLAViolation(
                sla_name='no_nan_ohlc',
                severity=SLASeverity.FATAL,
                measured_value=float(nan_count),
                threshold=0.0,
                message=f"OHLC contains {nan_count} NaN values"
            ))

    # SLA 2: Gap-based completeness (FATAL for InsideBar)
    if strategy_key == 'inside_bar':
        # Check lookback window for gaps
        if len(df) >= lookback_bars:
            lookback_window = df.tail(lookback_bars)
            gaps = _detect_gaps_in_window(lookback_window, timeframe)

            if gaps:
                logger.warning(f"Gap-based completeness: Found {len(gaps)} gaps in lookback window")
                violations.append(SLAViolation(
                    sla_name=f'{base_tf.lower()}_completeness',
                    severity=SLASeverity.FATAL,
                    measured_value=float(len(gaps)),
                    threshold=0.0,
                    message=f"Found {len(gaps)} gaps in {lookback_bars}-bar lookback window (FATAL for InsideBar)"
                ))
        else:
            # Not enough bars for lookback
            violations.append(SLAViolation(
                sla_name=f'{base_tf.lower()}_completeness',
                severity=SLASeverity.FATAL,
                measured_value=float(len(df)),
                threshold=float(lookback_bars),
                message=f"Insufficient data: {len(df)} bars < {lookback_bars} required lookback"
            ))

        # Ratio-based check (secondary, WARNING only)
        if len(df) > 0:
            expected_bars = _calculate_expected_bars(df.index, timeframe)
            actual_bars = len(df)
            completeness_ratio = actual_bars / expected_bars if expected_bars > 0 else 0

            if completeness_ratio < 0.99:  # 99% threshold
                violations.append(SLAViolation(
                    sla_name=f'{base_tf.lower()}_completeness_ratio',
                    severity=SLASeverity.WARNING,  # Warning only (gap-based is FATAL)
                    measured_value=completeness_ratio,
                    threshold=0.99,
                    message=f"Completeness: {completeness_ratio:.1%} (expected ~{expected_bars} bars, got {actual_bars})"
                ))

    # SLA 3: No duplicate timestamps (FATAL)
    if df.index.duplicated().any():
        dupe_count = df.index.duplicated().sum()
        violations.append(SLAViolation(
            sla_name='no_dupe_index',
            severity=SLASeverity.FATAL,
            measured_value=float(dupe_count),
            threshold=0.0,
            message=f"Found {dupe_count} duplicate timestamps"
        ))

    # Check if passed (no FATAL violations)
    fatal_violations = [v for v in violations if v.severity == SLASeverity.FATAL]
    passed = len(fatal_violations) == 0

    return SLAResult(
        passed=passed,
        violations=violations,
        base_timeframe=base_tf
    )


def _detect_gaps_in_window(df: pd.DataFrame, timeframe: str) -> List[pd.Timestamp]:
    """
    Detect missing bars in lookback window.

    InsideBar requires CONSECUTIVE bars:
    - Mother bar at index[-2]
    - Inside bar at index[-1]
    - Breakout check at current bar

    ANY gap invalidates pattern logic.

    Args:
        df: DataFrame with timezone-aware DatetimeIndex
        timeframe: M1/M5/M15

    Returns:
        List of missing timestamps
    """
    if len(df) < 2:
        return []

    # Expected frequency
    freq_map = {
        'M1': '1min',
        'M5': '5min',
        'M15': '15min'
    }
    freq = freq_map.get(timeframe, '5min')

    # Generate expected index (RTH only 9:30-16:00)
    try:
        expected_index = pd.date_range(
            start=df.index.min(),
            end=df.index.max(),
            freq=freq,
            tz=df.index.tz or "America/New_York"
        )
    except Exception as e:
        logger.warning(f"Error generating expected index: {e}")
        return []

    # Filter to RTH (9:30-16:00 ET)
    expected_index = expected_index[
        (expected_index.time >= pd.Timestamp("09:30").time()) &
        (expected_index.time <= pd.Timestamp("16:00").time())
    ]

    # Find missing timestamps
    missing = expected_index.difference(df.index)

    # Filter out weekends/holidays (if entire day is missing, assume holiday)
    # For now, return all missing (can be refined later)
    return list(missing)


def _calculate_expected_bars(index: pd.DatetimeIndex, timeframe: str) -> int:
    """
    Calculate expected bars for given date range.

    Args:
        index: DatetimeIndex
        timeframe: M1/M5/M15

    Returns:
        Expected number of bars (RTH only)
    """
    if len(index) == 0:
        return 0

    # Trading days in range
    days_span = (index.max() - index.min()).days + 1

    # Bars per RTH day (9:30-16:00 = 6.5 hours)
    bars_per_day = {
        'M1': 390,   # 6.5 * 60
        'M5': 78,    # 6.5 * 12
        'M15': 26    # 6.5 * 4
    }

    # Assume ~70% are trading days (252/365)
    trading_days = int(days_span * 0.7)

    return trading_days * bars_per_day.get(timeframe, 78)
