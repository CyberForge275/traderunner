"""
Data Coverage Gate

Validates that local parquet data covers requested backtest range.

ARCHITECTURE:
- Engine/Service layer (UI-independent)
- Fail-fast by default (auto_fetch=FALSE)
- Uses PyArrow fast metadata reads
- Returns result DTO (never raises)

POLICY:
- auto_fetch=FALSE default (explicit flag required)
- Coverage check before strategy execution
- Gap detected → FAILED_PRECONDITION (not silent auto-fetch)
"""

import logging
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)


class CoverageStatus(Enum):
    """Coverage check result status."""
    SUFFICIENT = "sufficient"
    GAP_DETECTED = "gap_detected"
    FETCH_FAILED = "fetch_failed"


@dataclass
class DateRange:
    """Date range with timezone-aware timestamps."""
    start: pd.Timestamp
    end: pd.Timestamp
    
    def __str__(self):
        return f"{self.start.date()} → {self.end.date()}"


@dataclass
class CoverageCheckResult:
    """
    Result of coverage check.
    
    ALWAYS returned (never raises), even on errors.
    """
    status: CoverageStatus
    requested_range: DateRange
    cached_range: Optional[DateRange]
    gap: Optional[DateRange] = None
    fetch_attempted: bool = False
    fetch_success: bool = False
    error_message: Optional[str] = None
    
    def to_dict(self):
        """Convert to dict for serialization."""
        return {
            'status': self.status.value,
            'requested_range': {
                'start': self.requested_range.start.isoformat(),
                'end': self.requested_range.end.isoformat()
            },
            'cached_range': {
                'start': self.cached_range.start.isoformat(),
                'end': self.cached_range.end.isoformat()
            } if self.cached_range else None,
            'gap': {
                'start': self.gap.start.isoformat(),
                'end': self.gap.end.isoformat()
            } if self.gap else None,
            'fetch_attempted': self.fetch_attempted,
            'fetch_success': self.fetch_success,
            'error_message': self.error_message
        }


def check_coverage(
    symbol: str,
    timeframe: str,
    requested_end: pd.Timestamp,
    lookback_days: int,
    market_tz: str = "America/New_York",
    auto_fetch: bool = False  # ⚠️ DEFAULT FALSE (fail-fast policy)
) -> CoverageCheckResult:
    """
    Check if local intraday data covers requested range.
    
    ⚠️ CRITICAL: auto_fetch=False by default (fail-fast policy)
    Auto-fetch only via explicit flag/config.
    
    Args:
        symbol: Stock symbol
        timeframe: M1, M5, M15
        requested_end: End timestamp for backtest
        lookback_days: Lookback in calendar days
        market_tz: Market timezone (default: America/New_York)
        auto_fetch: If True, attempt to fetch missing data (DEFAULT FALSE)
    
    Returns:
        CoverageCheckResult (always, never raises)
    
    Logic:
    1. Load cached parquet metadata (fast - PyArrow)
    2. Calculate requested_start from lookback_days
    3. Check: cached_min <= requested_start AND cached_max >= requested_end
    4. If gap detected:
       - auto_fetch=False (default): return GAP_DETECTED status
       - auto_fetch=True: attempt fetch, verify, return result
    """
    # INT Runtime: Skip coverage checks if env var set
    # This allows backtest execution without trading_dashboard dependency
    import os
    skip_coverage = os.environ.get('AXIOM_BT_SKIP_COVERAGE') or os.environ.get('AXIOM_BT_SKIP_PRECONDITIONS')
    if skip_coverage and skip_coverage.lower() in ('1', 'true', 'yes', 'on'):
        logger.warning("Coverage check SKIPPED via environment variable (INT runtime mode)")
        requested_range = DateRange(
            start=requested_end - pd.Timedelta(days=lookback_days),
            end=requested_end
        )
        return CoverageCheckResult(
            status=CoverageStatus.SUFFICIENT,
            requested_range=requested_range,
            cached_range=requested_range,  # Fake cached range to satisfy caller
        )
    
    try:
        from trading_dashboard.utils.parquet_meta_reader import read_parquet_metadata_fast
        from axiom_bt.fs import DATA_M1, DATA_M5, DATA_M15
        
        # Get parquet path
        path_map = {
            'M1': DATA_M1,
            'M5': DATA_M5,
            'M15': DATA_M15
        }
        data_dir = path_map.get(timeframe)
        if not data_dir:
            return CoverageCheckResult(
                status=CoverageStatus.GAP_DETECTED,
                requested_range=DateRange(
                    start=requested_end - pd.Timedelta(days=lookback_days),
                    end=requested_end
                ),
                cached_range=None,
                error_message=f"Unknown timeframe: {timeframe}"
            )
        
        parquet_path = data_dir / f"{symbol}.parquet"
        
        # Fast metadata read (O(1), no DataFrame load)
        logger.debug(f"Checking coverage for {symbol} {timeframe} (path={parquet_path})")
        meta = read_parquet_metadata_fast(parquet_path)
        
        # Calculate requested range
        requested_start = _calculate_start_date(requested_end, lookback_days, market_tz)
        requested_range = DateRange(start=requested_start, end=requested_end)
        
        if not meta.exists:
            logger.warning(f"Coverage gap: {symbol} {timeframe} parquet not found")
            return CoverageCheckResult(
                status=CoverageStatus.GAP_DETECTED,
                requested_range=requested_range,
                cached_range=None,
                gap=requested_range
            )
        
        cached_range = DateRange(start=meta.first_ts, end=meta.last_ts) if meta.first_ts else None
        
        # Check coverage
        if cached_range and cached_range.start <= requested_start and cached_range.end >= requested_end:
            logger.info(f"Coverage sufficient: {symbol} {timeframe} {cached_range}")
            return CoverageCheckResult(
                status=CoverageStatus.SUFFICIENT,
                requested_range=requested_range,
                cached_range=cached_range
            )
        
        # Gap detected
        gap = _calculate_gap(requested_range, cached_range)
        logger.warning(f"Coverage gap detected: {symbol} {timeframe} gap={gap}")
        
        if not auto_fetch:
            # Fail-fast (default policy)
            logger.info(f"auto_fetch=False, returning GAP_DETECTED")
            return CoverageCheckResult(
                status=CoverageStatus.GAP_DETECTED,
                requested_range=requested_range,
                cached_range=cached_range,
                gap=gap
            )
        
        # Auto-fetch enabled (explicit flag)
        logger.info(f"auto_fetch=True, attempting to fetch missing data")
        try:
            _fetch_missing_range(symbol, timeframe, gap, market_tz)
            
            # Verify after fetch
            meta_after = read_parquet_metadata_fast(parquet_path)
            if meta_after.first_ts <= requested_start and meta_after.last_ts >= requested_end:
                logger.info(f"Fetch successful, coverage now sufficient")
                return CoverageCheckResult(
                    status=CoverageStatus.SUFFICIENT,
                    requested_range=requested_range,
                    cached_range=DateRange(start=meta_after.first_ts, end=meta_after.last_ts),
                    fetch_attempted=True,
                    fetch_success=True
                )
            else:
                logger.error(f"Fetch completed but coverage still insufficient")
                return CoverageCheckResult(
                    status=CoverageStatus.FETCH_FAILED,
                    requested_range=requested_range,
                    cached_range=DateRange(start=meta_after.first_ts, end=meta_after.last_ts) if meta_after.first_ts else None,
                    gap=gap,
                    fetch_attempted=True,
                    fetch_success=False,
                    error_message="Fetch completed but coverage still insufficient"
                )
        except Exception as fetch_error:
            logger.error(f"Fetch failed: {fetch_error}", exc_info=True)
            return CoverageCheckResult(
                status=CoverageStatus.FETCH_FAILED,
                requested_range=requested_range,
                cached_range=cached_range,
                gap=gap,
                fetch_attempted=True,
                fetch_success=False,
                error_message=str(fetch_error)
            )
    
    except Exception as e:
        logger.error(f"Coverage check failed: {e}", exc_info=True)
        return CoverageCheckResult(
            status=CoverageStatus.GAP_DETECTED,
            requested_range=DateRange(
                start=requested_end - pd.Timedelta(days=lookback_days),
                end=requested_end
            ),
            cached_range=None,
            error_message=str(e)
        )


def _calculate_start_date(
    end: pd.Timestamp,
    lookback_days: int,
    tz: str = "America/New_York"
) -> pd.Timestamp:
    """
    Calculate start date by going back N calendar days.
    
    Note: Uses calendar days, not trading days (conservative approach).
    """
    start = end - pd.Timedelta(days=lookback_days)
    # Ensure timezone aware
    if start.tz is None:
        start = start.tz_localize(tz)
    return start


def _calculate_gap(
    requested: DateRange,
    cached: Optional[DateRange]
) -> Optional[DateRange]:
    """Calculate missing data range."""
    if not cached:
        return requested
    
    # Gap at end (most common)
    if cached.end < requested.end:
        return DateRange(start=cached.end, end=requested.end)
    
    # Gap at start
    elif cached.start > requested.start:
        return DateRange(start=requested.start, end=cached.start)
    
    return None


def _fetch_missing_range(
    symbol: str,
    tf: str,
    gap: DateRange,
    tz: str
):
    """
    Fetch missing data range via EODHD.
    
    Raises on fetch failure.
    """
    from axiom_bt.cli_data import fetch_intraday_1m_to_parquet, resample_m1
    from axiom_bt.fs import DATA_M1, DATA_M5, DATA_M15
    
    logger.info(f"Fetching {symbol} M1 for gap {gap}")
    
    # Fetch M1 base data
    fetch_intraday_1m_to_parquet(
        symbol,
        exchange="US",
        start=gap.start.date().isoformat(),
        end=gap.end.date().isoformat(),
        output_dir=DATA_M1,
        tz=tz
    )
    
    # Resample if needed
    m1_path = DATA_M1 / f"{symbol}.parquet"
    
    if tf == "M5":
        logger.info(f"Resampling {symbol} M1 → M5")
        resample_m1(m1_path, DATA_M5, interval="5min", tz=tz)
    elif tf == "M15":
        logger.info(f"Resampling {symbol} M1 → M15")
        resample_m1(m1_path, DATA_M15, interval="15min", tz=tz)
