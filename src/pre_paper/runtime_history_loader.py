"""
Runtime History Loader

Ensures runtime history is sufficient for strategy execution.

CRITICAL CONTRACT:
- Strategy execution ONLY if ensure_history() returns SUFFICIENT
- Otherwise: NO-SIGNALS with logged reason
"""

import logging
from pathlib import Path
from typing import Optional
import pandas as pd

from pre_paper.history_status import HistoryStatus, HistoryCheckResult, DateRange
from pre_paper.historical_provider import HistoricalProvider
from pre_paper.cache.sqlite_cache import SQLiteCache

logger = logging.getLogger(__name__)


def ensure_history(
    symbol: str,
    tf: str,
    base_tf_used: str,
    required_start_ts: pd.Timestamp,
    required_end_ts: pd.Timestamp,
    cache_db_path: Path,
    historical_provider: Optional[HistoricalProvider] = None,
    auto_backfill: bool = False
) -> HistoryCheckResult:
    """
    Ensure runtime history is sufficient for strategy execution.

    Workflow:
    1. Check pre_paper_cache.db for required window
    2. If complete → SUFFICIENT
    3. If gaps:
       - If auto_backfill=True: fetch missing ranges
       - Else: DEGRADED
    4. Return HistoryCheckResult

    Args:
        symbol: Stock symbol
        tf: Target timeframe (M5/M15)
        base_tf_used: Base timeframe from manifest
        required_start_ts: Required start (market_tz)
        required_end_ts: Required end (market_tz)
        cache_db_path: Path to pre_paper_cache.db
        historical_provider: Provider for backfilling
        auto_backfill: Enable automatic backfill

    Returns:
        HistoryCheckResult with status
    """
    # Open cache
    cache = SQLiteCache(cache_db_path)

    try:
        # Get cached range
        cached_range = cache.get_range(symbol, tf)

        if cached_range is None:
            # No data in cache
            logger.warning(f"No cached data for {symbol} {tf}")

            if auto_backfill and historical_provider:
                # Attempt backfill
                logger.info(f"Backfilling {symbol} {tf}: {required_start_ts} → {required_end_ts}")

                try:
                    df = historical_provider.fetch_bars(symbol, tf, required_start_ts, required_end_ts)

                    if len(df) > 0:
                        # Store in cache
                        cache.append_bars(symbol, tf, df, source="backfill")
                        logger.info(f"Backfilled {len(df)} bars for {symbol} {tf}")

                        # Re-check cache
                        cached_range = cache.get_range(symbol, tf)

                        if cached_range:
                            cached_start_ts, cached_end_ts = cached_range

                            # Check if now sufficient
                            if cached_start_ts <= required_start_ts and cached_end_ts >= required_end_ts:
                                return HistoryCheckResult(
                                    status=HistoryStatus.SUFFICIENT,
                                    symbol=symbol,
                                    tf=tf,
                                    base_tf_used=base_tf_used,
                                    required_start_ts=required_start_ts,
                                    required_end_ts=required_end_ts,
                                    cached_start_ts=cached_start_ts,
                                    cached_end_ts=cached_end_ts,
                                    gaps=[],
                                    fetch_attempted=True,
                                    fetch_success=True,
                                    reason=None
                                )
                            else:
                                # Still gaps after backfill
                                gaps = _calculate_gaps(required_start_ts, required_end_ts, cached_start_ts, cached_end_ts)

                                return HistoryCheckResult(
                                    status=HistoryStatus.LOADING,
                                    symbol=symbol,
                                    tf=tf,
                                    base_tf_used=base_tf_used,
                                    required_start_ts=required_start_ts,
                                    required_end_ts=required_end_ts,
                                    cached_start_ts=cached_start_ts,
                                    cached_end_ts=cached_end_ts,
                                    gaps=gaps,
                                    fetch_attempted=True,
                                    fetch_success=True,
                                    reason=f"Partial backfill complete, gaps remain: {gaps[0].start} → {gaps[0].end}"
                                )
                    else:
                        # Fetch returned empty
                        logger.warning(f"Backfill returned no data for {symbol} {tf}")

                        return HistoryCheckResult(
                            status=HistoryStatus.DEGRADED,
                            symbol=symbol,
                            tf=tf,
                            base_tf_used=base_tf_used,
                            required_start_ts=required_start_ts,
                            required_end_ts=required_end_ts,
                            cached_start_ts=None,
                            cached_end_ts=None,
                            gaps=[DateRange(required_start_ts, required_end_ts)],
                            fetch_attempted=True,
                            fetch_success=False,
                            reason="Backfill returned no data"
                        )

                except Exception as e:
                    logger.error(f"Backfill failed for {symbol} {tf}: {e}")

                    return HistoryCheckResult(
                        status=HistoryStatus.DEGRADED,
                        symbol=symbol,
                        tf=tf,
                        base_tf_used=base_tf_used,
                        required_start_ts=required_start_ts,
                        required_end_ts=required_end_ts,
                        cached_start_ts=None,
                        cached_end_ts=None,
                        gaps=[DateRange(required_start_ts, required_end_ts)],
                        fetch_attempted=True,
                        fetch_success=False,
                        reason=f"Backfill error: {str(e)}"
                    )
            else:
                # No backfill, degraded
                return HistoryCheckResult(
                    status=HistoryStatus.DEGRADED,
                    symbol=symbol,
                    tf=tf,
                    base_tf_used=base_tf_used,
                    required_start_ts=required_start_ts,
                    required_end_ts=required_end_ts,
                    cached_start_ts=None,
                    cached_end_ts=None,
                    gaps=[DateRange(required_start_ts, required_end_ts)],
                    fetch_attempted=False,
                    fetch_success=False,
                    reason="No cached data, auto_backfill disabled"
                )

        # Cache has data - check coverage
        cached_start_ts, cached_end_ts = cached_range

        # Check if cache covers required window
        if cached_start_ts <= required_start_ts and cached_end_ts >= required_end_ts:
            # SUFFICIENT
            logger.info(f"History SUFFICIENT for {symbol} {tf}")

            return HistoryCheckResult(
                status=HistoryStatus.SUFFICIENT,
                symbol=symbol,
                tf=tf,
                base_tf_used=base_tf_used,
                required_start_ts=required_start_ts,
                required_end_ts=required_end_ts,
                cached_start_ts=cached_start_ts,
                cached_end_ts=cached_end_ts,
                gaps=[],
                fetch_attempted=False,
                fetch_success=False,
                reason=None
            )
        else:
            # Gaps exist
            gaps = _calculate_gaps(required_start_ts, required_end_ts, cached_start_ts, cached_end_ts)

            logger.warning(f"History gaps for {symbol} {tf}: {gaps}")

            # Attempt backfill if enabled
            if auto_backfill and historical_provider and len(gaps) > 0:
                # Backfill first gap (simplified for PoC)
                gap = gaps[0]

                logger.info(f"Backfilling gap: {symbol} {tf}: {gap.start} → {gap.end}")

                try:
                    df = historical_provider.fetch_bars(symbol, tf, gap.start, gap.end)

                    if len(df) > 0:
                        cache.append_bars(symbol, tf, df, source="backfill")
                        logger.info(f"Backfilled {len(df)} bars")

                        # Return LOADING (gap being filled)
                        return HistoryCheckResult(
                            status=HistoryStatus.LOADING,
                            symbol=symbol,
                            tf=tf,
                            base_tf_used=base_tf_used,
                            required_start_ts=required_start_ts,
                            required_end_ts=required_end_ts,
                            cached_start_ts=cached_start_ts,
                            cached_end_ts=cached_end_ts,
                            gaps=gaps,
                            fetch_attempted=True,
                            fetch_success=True,
                            reason=f"Backfilling gap: {gap.start} → {gap.end}"
                        )
                    else:
                        return HistoryCheckResult(
                            status=HistoryStatus.DEGRADED,
                            symbol=symbol,
                            tf=tf,
                            base_tf_used=base_tf_used,
                            required_start_ts=required_start_ts,
                            required_end_ts=required_end_ts,
                            cached_start_ts=cached_start_ts,
                            cached_end_ts=cached_end_ts,
                            gaps=gaps,
                            fetch_attempted=True,
                            fetch_success=False,
                            reason=f"Backfill returned no data for gap: {gap.start} → {gap.end}"
                        )

                except Exception as e:
                    logger.error(f"Backfill failed: {e}")

                    return HistoryCheckResult(
                        status=HistoryStatus.DEGRADED,
                        symbol=symbol,
                        tf=tf,
                        base_tf_used=base_tf_used,
                        required_start_ts=required_start_ts,
                        required_end_ts=required_end_ts,
                        cached_start_ts=cached_start_ts,
                        cached_end_ts=cached_end_ts,
                        gaps=gaps,
                        fetch_attempted=True,
                        fetch_success=False,
                        reason=f"Backfill error: {str(e)}"
                    )
            else:
                # No backfill - DEGRADED
                return HistoryCheckResult(
                    status=HistoryStatus.DEGRADED,
                    symbol=symbol,
                    tf=tf,
                    base_tf_used=base_tf_used,
                    required_start_ts=required_start_ts,
                    required_end_ts=required_end_ts,
                    cached_start_ts=cached_start_ts,
                    cached_end_ts=cached_end_ts,
                    gaps=gaps,
                    fetch_attempted=False,
                    fetch_success=False,
                    reason=f"History gaps exist, auto_backfill disabled: {gaps[0].start} → {gaps[0].end}"
                )

    finally:
        cache.close()


def _calculate_gaps(
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
    cached_start: pd.Timestamp,
    cached_end: pd.Timestamp
) -> list[DateRange]:
    """Calculate gaps between required and cached ranges."""
    gaps = []

    # Gap before cached range
    if cached_start > required_start:
        gaps.append(DateRange(required_start, cached_start))

    # Gap after cached range
    if cached_end < required_end:
        gaps.append(DateRange(cached_end, required_end))

    return gaps
