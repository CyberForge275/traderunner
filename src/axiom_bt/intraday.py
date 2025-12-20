from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from axiom_bt.fs import DATA_M1, DATA_M5, DATA_M15, DATA_D1, ensure_layout
from axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet, resample_m1

import logging
logger = logging.getLogger(__name__)


def get_eodhd_token_with_guard() -> str:
    """Get EODHD API token with strict validation.
    
    Raises:
        ValueError: If token is missing or set to 'demo'
    """
    import os
    token = os.getenv("EODHD_API_TOKEN")
    
    if not token:
        raise ValueError(
            "EODHD_API_TOKEN not found in environment. "
            "Configure token in /opt/trading/marketdata-stream/.env"
        )
    
    if token.lower() == "demo":
        raise ValueError(
            "EODHD_API_TOKEN is set to 'demo'. "
            "This is forbidden. Use your actual API token."
        )
    
    return token


def check_local_m1_coverage(
    symbol: str,
    start: str,
    end: str,
    tz: str = "America/New_York"
) -> dict:
    """Check how many days of M1 data are available locally and identify precise gaps.
    
    This function determines exactly which data is missing by comparing the requested
    range against existing data. It returns precise gap boundaries to avoid re-fetching
    data that already exists.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        start: Start date ISO format (e.g., "2024-09-28")
        end: End date ISO format (e.g., "2024-12-17")
        tz: Timezone for date calculations
    
    Returns:
        Dict with keys:
            - available_days: int - Days of data currently in file
            - requested_days: int - Days of data needed
            - has_gap: bool - True if any data is missing
            - earliest_data: str (ISO) - Earliest date in existing data (if exists)
            - latest_data: str (ISO) - Latest date in existing data (if exists)
            - gaps: list[dict] - List of missing ranges, each with:
                - gap_start: str (ISO)
                - gap_end: str (ISO)
                - gap_days: int
    
    Example:
        >>> # Existing data: 2024-12-01 to 2024-12-19
        >>> # Requested: 2024-10-01 to 2024-12-19
        >>> result = check_local_m1_coverage('TSLA', '2024-10-01', '2024-12-19')
        >>> result['gaps']
        [{'gap_start': '2024-10-01', 'gap_end': '2024-11-30', 'gap_days': 61}]
    """
    from datetime import datetime, timedelta
    
    m1_path = DATA_M1 / f"{symbol}.parquet"
    
    requested_start = datetime.fromisoformat(start).date()
    requested_end = datetime.fromisoformat(end).date()
    requested_days = (requested_end - requested_start).days + 1
    
    if not m1_path.exists():
        # No data at all - entire range is a gap
        return {
            "available_days": 0,
            "requested_days": requested_days,
            "has_gap": True,
            "gaps": [{
                "gap_start": start,
                "gap_end": end,
                "gap_days": requested_days
            }]
        }
    
    # Load existing M1 data
    try:
        df = pd.read_parquet(m1_path)
        
        # Get index in UTC (critical: keep in UTC for date() calculations)
        # EODHD provides UTC timestamps, so we extract dates in UTC
        if "timestamp" in df.columns:
            df_index_utc = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        elif isinstance(df.index, pd.DatetimeIndex):
            if df.index.tz is None:
                df_index_utc = pd.to_datetime(df.index, errors="coerce", utc=True)
            else:
                df_index_utc = df.index.tz_convert("UTC")
        else:
            # Can't determine index, assume entire range is gap
            return {
                "available_days": 0,
                "requested_days": requested_days,
                "has_gap": True,
                "gaps": [{
                    "gap_start": start,
                    "gap_end": end,
                    "gap_days": requested_days
                }]
            }
        
        # Get date range of existing data (in UTC!)
        # IMPORTANT: .date() on UTC time to avoid timezone shift bugs
        earliest = df_index_utc.min().date()
        latest = df_index_utc.max().date()
        available_days = (latest - earliest).days + 1
        
        # Identify precise gaps
        gaps = []
        
        # Gap 1: Before existing data (if requested_start < earliest)
        if requested_start < earliest:
            gap_end = earliest - timedelta(days=1)
            gap_days = (gap_end - requested_start).days + 1
            gaps.append({
                "gap_start": requested_start.isoformat(),
                "gap_end": gap_end.isoformat(),
                "gap_days": gap_days,
                "reason": "before_existing_data"
            })
        
        # Gap 2: After existing data (if requested_end > latest)
        if requested_end > latest:
            gap_start = latest + timedelta(days=1)
            gap_days = (requested_end - gap_start).days + 1
            gaps.append({
                "gap_start": gap_start.isoformat(),
                "gap_end": requested_end.isoformat(),
                "gap_days": gap_days,
                "reason": "after_existing_data"
            })
        
        # Build result
        result = {
            "available_days": available_days,
            "requested_days": requested_days,
            "has_gap": len(gaps) > 0,
            "earliest_data": earliest.isoformat(),
            "latest_data": latest.isoformat(),
            "gaps": gaps
        }
        
        return result
    
    except Exception as e:
        logger.warning(f"Could not read {m1_path} for coverage check: {e}")
        # On error, assume entire range is gap to be safe
        return {
            "available_days": 0,
            "requested_days": requested_days,
            "has_gap": True,
            "gaps": [{
                "gap_start": start,
                "gap_end": end,
                "gap_days": requested_days,
                "reason": "error_reading_file"
            }]
        }


class Timeframe(str, Enum):
    """Supported intraday timeframes for the central store."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"


@dataclass(frozen=True)
class IntradaySpec:
    """Specification for ensuring intraday data.

    Attributes
    ----------
    symbols:
        Iterable of ticker strings; will be normalized to upper-case.
    start:
        Inclusive start date (YYYY-MM-DD or datetime.date).
    end:
        Inclusive end date (YYYY-MM-DD or datetime.date).
    timeframe:
        Target bar timeframe (M1/M5/M15); controls which resamples are created.
    tz:
        IANA timezone name in which bars are interpreted and returned.
    """

    symbols: Iterable[str]
    start: str | date
    end: str | date
    timeframe: Timeframe
    tz: str = "America/New_York"


class IntradayStore:
    """Central service for ensuring and loading intraday OHLCV data.

    All strategies should use this instead of accessing parquet files directly.
    """

    def __init__(self, *, default_tz: str = "America/New_York") -> None:
        ensure_layout()
        self._default_tz = default_tz

    def ensure(
        self,
        spec: IntradaySpec,
        *,
        force: bool = False,
        use_sample: bool = False,
        auto_fill_gaps: bool = True,
    ) -> Dict[str, List[str]]:
        """Ensure required intraday data exists on disk.
        
        NEW: Now checks local coverage and auto-fills gaps from EODHD if enabled.

        Args:
            spec: IntradaySpec with symbols, date range, timeframe
            force: Force rebuild even if cache exists
            use_sample: Use sample data (testing only)
            auto_fill_gaps: If True, automatically fetch missing data from EODHD
            
        Returns:
            Dict mapping symbol -> list of actions taken
        """

        symbols = sorted({s.strip().upper() for s in spec.symbols if s.strip()})
        if not symbols:
            return {}

        start_str = _to_date_str(spec.start)
        end_str = _to_date_str(spec.end)
        tz = spec.tz or self._default_tz

        actions: Dict[str, List[str]] = {}

        for symbol in symbols:
            sym_actions: List[str] = []
            m1_path = DATA_M1 / f"{symbol}.parquet"
            
            # NEW: Check coverage before deciding to fetch
            if not force and auto_fill_gaps:
                coverage = check_local_m1_coverage(
                    symbol=symbol,
                    start=start_str,
                    end=end_str,
                    tz=tz
                )
                
                if coverage["has_gap"]:
                    # Gap(s) detected - fetch only missing data
                    logger.info(
                        f"[{symbol}] Gap detected: have {coverage['available_days']} days, "
                        f"need {coverage['requested_days']} days. "
                        f"Found {len(coverage['gaps'])} gap(s)."
                    )
                    
                    # Fetch each gap separately
                    for gap in coverage["gaps"]:
                        logger.info(
                            f"[{symbol}] Fetching gap: {gap['gap_start']} to {gap['gap_end']} "
                            f"({gap['gap_days']} days, reason: {gap.get('reason', 'unknown')})"
                        )
                        
                        # Fetch gap data to temp location first
                        import tempfile
                        import shutil
                        temp_dir = Path(tempfile.mkdtemp(prefix="eodhd_gap_"))
                        
                        try:
                            gap_path = fetch_intraday_1m_to_parquet(
                                symbol=symbol,
                                exchange="US",
                                start_date=gap['gap_start'],
                                end_date=gap['gap_end'],
                                out_dir=temp_dir,
                                tz=tz,
                                use_sample=use_sample,
                                save_raw=True,   # Save raw data with Pre/After-Market
                                filter_rth=True, # Filter to RTH for final output
                            )
                            
                            # Merge with existing data if file exists
                            if m1_path.exists():
                                existing_df = pd.read_parquet(m1_path)
                                gap_df = pd.read_parquet(gap_path)
                                
                                # Merge
                                merged_df = pd.concat([existing_df, gap_df])
                                merged_df = merged_df.sort_index().drop_duplicates()
                                
                                # Save merged result
                                merged_df.to_parquet(m1_path)
                                logger.info(
                                    f"[{symbol}] Merged {len(gap_df)} new rows with "
                                    f"{len(existing_df)} existing → {len(merged_df)} total"
                                )
                            else:
                                # No existing file, just move gap data
                                shutil.move(str(gap_path), str(m1_path))
                                logger.info(f"[{symbol}] Created new M1 file with gap data")
                        
                        finally:
                            # Clean up temp dir
                            if temp_dir.exists():
                                shutil.rmtree(temp_dir)
                    
                    sym_actions.append(f"gap_fill_{len(coverage['gaps'])}_gaps_{sum(g['gap_days'] for g in coverage['gaps'])}_days")
                else:
                    # Sufficient coverage
                    logger.info(
                        f"[{symbol}] Sufficient M1 coverage: {coverage['available_days']} days"
                    )
                    sym_actions.append("use_cached_m1")
            
            elif force or not m1_path.exists():
                # Original behavior: force rebuild or doesn't exist
                fetch_intraday_1m_to_parquet(
                    symbol=symbol,
                    exchange="US",
                    start_date=start_str,
                    end_date=end_str,
                    out_dir=DATA_M1,
                    tz=tz,
                    use_sample=use_sample,
                    save_raw=True,   # Save raw data with Pre/After-Market
                    filter_rth=True, # Filter to RTH for final output
                )
                sym_actions.append("fetch_m1")
            else:
                sym_actions.append("use_cached_m1")

            # Resample to M5, M15 (existing logic)
            resample_m1(m1_path, DATA_M5, interval="5min", tz=tz)
            sym_actions.append("resample_m5")

            if spec.timeframe == Timeframe.M15:
                resample_m1(m1_path, DATA_M15, interval="15min", tz=tz)
                sym_actions.append("resample_m15")

            actions[symbol] = sym_actions

        # Evidence logging after all symbols processed
        if actions:
            logger.info(f"[ensure] Summary for {len(symbols)} symbol(s):")
            for sym, acts in actions.items():
                logger.info(f"  {sym}: {' → '.join(acts)}")
                
                # Log data quality for symbols that were fetched/filled
                if any("fetch" in act or "gap_fill" in act for act in acts):
                    m1_file = DATA_M1 / f"{sym}.parquet"
                    if m1_file.exists():
                        try:
                            df_check = pd.read_parquet(m1_file)
                            
                            # Get index
                            if "timestamp" in df_check.columns:
                                idx = pd.to_datetime(df_check["timestamp"], utc=True).dt.tz_convert(tz)
                            else:
                                idx = df_check.index
                                if idx.tz is None:
                                    idx = pd.to_datetime(idx, utc=True).dt.tz_convert(tz)
                                else:
                                    idx = idx.tz_convert(tz)
                            
                            # Quality checks
                            ohlc_cols = [c for c in ["open", "high", "low", "close", "Open", "High", "Low", "Close"] if c in df_check.columns]
                            if ohlc_cols:
                                nan_count = df_check[ohlc_cols].isna().all(axis=1).sum()
                                nan_pct = (nan_count / len(df_check)) * 100 if len(df_check) > 0 else 0
                            else:
                                nan_pct = 0
                            
                            is_monotonic = idx.is_monotonic_increasing
                            is_unique = not idx.duplicated().any()
                            
                            logger.info(
                                f"  {sym} M1: {len(df_check)} rows, "
                                f"NaN={nan_pct:.1f}%, "
                                f"range={idx.min().date()} to {idx.max().date()}, "
                                f"tz={idx.tz}, "
                                f"monotonic={'✓' if is_monotonic else '✗'}, "
                                f"unique={'✓' if is_unique else '✗'}"
                            )
                        except Exception as e:
                            logger.warning(f"  {sym}: Could not verify M1 quality: {e}")

        return actions

    def load(
        self,
        symbol: str,
        *,
        timeframe: Timeframe,
        tz: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load normalized intraday OHLCV for one symbol/timeframe."""

        symbol = symbol.strip().upper()
        path = self.path_for(symbol, timeframe=timeframe)

        if not path.exists():
            raise FileNotFoundError(f"Intraday parquet not found: {path}")

        # Load parquet file
        frame = pd.read_parquet(path)
        
        # Load and normalize OHLCV
        df = _normalize_ohlcv_frame(frame, target_tz=tz or self._default_tz, symbol=symbol)

        # v2 Data Contract Validation
        import os
        if os.environ.get("ENABLE_CONTRACTS", "false").lower() == "true":
            from axiom_bt.contracts import IntradayFrameSpec
            # Contract expects TitleCase columns, but we use lowercase internally
            validation_view = df.rename(columns={
                "open": "Open", "high": "High", "low": "Low", 
                "close": "Close", "volume": "Volume"
            })
            IntradayFrameSpec.assert_valid(validation_view, tz=tz or self._default_tz)

        return df

    def has_symbol(self, symbol: str, *, timeframe: Timeframe) -> bool:
        symbol = symbol.strip().upper()
        return self.path_for(symbol, timeframe=timeframe).exists()

    def path_for(self, symbol: str, *, timeframe: Timeframe) -> Path:
        symbol = symbol.strip().upper()
        if timeframe == Timeframe.M1:
            base = DATA_M1
        elif timeframe == Timeframe.M5:
            base = DATA_M5
        elif timeframe == Timeframe.M15:
            base = DATA_M15
        else:
            raise ValueError(f"Unsupported timeframe for intraday store: {timeframe}")
        return base / f"{symbol}.parquet"


def _to_date_str(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_ohlcv_frame(frame: pd.DataFrame, target_tz: str, symbol: str = "UNKNOWN") -> pd.DataFrame:
    """Normalize raw parquet to a standard OHLCV frame.

    - Accepts either a datetime index or a 'timestamp' column.
    - Ensures tz-aware index in ``target_tz``.
    - Ensures columns: open, high, low, close, volume.
    - DEFENSIVE: Merges duplicate uppercase/lowercase columns
    - LOGS: Column transformations and NaN statistics for debugging
    """

    df = frame.copy()
    original_columns = list(df.columns)
    had_duplicates = False
    merge_log = []

    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df.drop(columns=["timestamp"])
        df.index = ts
    elif isinstance(df.index, pd.DatetimeIndex):
        ts = pd.to_datetime(df.index, errors="coerce", utc=True)
        df.index = ts
    else:
        raise ValueError("Frame must have datetime index or 'timestamp' column")

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    df = df.sort_index()
    df.index = df.index.tz_convert(target_tz)
    df.index.name = "timestamp"

    # Handle duplicate columns (Capitalized + lowercase) by merging:
    # Use Capitalized where available, fall back to lowercase where Capitalized is NaN
    required_raw = ["open", "high", "low", "close", "volume"]

    result_cols: Dict[str, pd.Series] = {}
    column_mapping: Dict[str, str] = {}
    for name in required_raw:
        cap_name = name.capitalize()
        low_name = name.lower()

        has_cap = cap_name in df.columns
        has_low = low_name in df.columns

        if has_cap and has_low:
            # DEBUG: Duplicate column detected
            had_duplicates = True
            cap_count = df[cap_name].notna().sum()
            low_count = df[low_name].notna().sum()
            
            series = df[cap_name].fillna(df[low_name])
            source_name = cap_name
            
            merge_log.append(f"{cap_name}({cap_count})+{low_name}({low_count})→{name}")
            
        elif has_cap:
            series = df[cap_name]
            source_name = cap_name
        elif has_low:
            series = df[low_name]
            source_name = low_name
        else:
            raise ValueError(
                f"Intraday parquet missing required column: {name} (neither {cap_name} nor {low_name} found)"
            )

        result_cols[name] = series
        column_mapping[name] = source_name

    ordered = pd.DataFrame(result_cols, index=df.index)
    ordered.columns = required_raw

    # Calculate NaN statistics for OHLC (not volume, that can be 0)
    nan_stats = {}
    for col in ["open", "high", "low", "close"]:
        nan_count = ordered[col].isna().sum()
        nan_pct = (nan_count / len(ordered) * 100) if len(ordered) > 0 else 0
        nan_stats[col] = {'count': nan_count, 'pct': nan_pct}
    
    # DEBUG LOGGING
    logger.debug(
        f"[OHLCV_NORMALIZE] symbol={symbol} rows={len(ordered)} "
        f"columns_before={original_columns} columns_after={list(ordered.columns)} "
        f"had_duplicates={had_duplicates}"
    )
    
    if merge_log:
        logger.info(
            f"[OHLCV_NORMALIZE] {symbol}: Merged duplicate columns: {', '.join(merge_log)}"
        )
    
    if nan_stats:
        nan_summary = ", ".join([f"{k}={v['count']}({v['pct']:.1f}%)" for k, v in nan_stats.items() if v['count'] > 0])
        if nan_summary:
            logger.warning(
                f"[OHLCV_NORMALIZE] {symbol}: NaN detected: {nan_summary}"
            )

    # Attach metadata so downstream debug tooling can report how the
    # canonical OHLCV view was derived from the raw source.
    ordered.attrs["ohlcv_raw_columns"] = original_columns
    ordered.attrs["ohlcv_canonical_columns"] = required_raw
    ordered.attrs["ohlcv_column_mapping"] = column_mapping
    ordered.attrs["ohlcv_had_duplicates"] = had_duplicates
    ordered.attrs["ohlcv_nan_stats"] = nan_stats

    return ordered
