"""Data fetcher for pipeline: wraps IntradayStore/Spec and snapshots bars.

Reads/writes only via existing SSOT storage; does not change parquet generation logic.
Supports intraday (M1/M5/M15/H1) via IntradayStore.ensure (M1 as base) and daily (D1) via existing cached file.
H1 is derived by resampling M1 locally (no external fetch).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict

import pandas as pd

from axiom_bt.intraday import (
    IntradaySpec,
    IntradayStore,
    Timeframe,
    _normalize_ohlcv_frame,
    check_local_m1_coverage,
)
from axiom_bt.fs import DATA_D1
from .data_prep import _sha256_file

logger = logging.getLogger(__name__)


class DataFetcherError(RuntimeError):
    """Raised when bars cannot be ensured or snapshotted."""


class MissingHistoricalDataError(DataFetcherError):
    """Raised when required historical bars are missing and auto-fetch is disabled."""


def _timeframe_minutes(timeframe: str) -> int:
    tf = timeframe.upper()
    if tf == "M1":
        return 1
    if tf == "M5":
        return 5
    if tf == "M15":
        return 15
    if tf == "H1":
        return 60
    if tf == "D1":
        return 60 * 24
    raise DataFetcherError(f"unsupported timeframe '{timeframe}' (expected M1/M5/M15/H1/D1)")


def _resolve_timeframe(timeframe: str) -> Timeframe:
    tf = timeframe.upper()
    try:
        return Timeframe[tf]
    except Exception as exc:
        raise DataFetcherError(f"unsupported timeframe '{timeframe}' (expected M1/M5/M15/D1)") from exc


def ensure_and_snapshot_bars(
    *,
    run_dir: Path,
    symbol: str,
    timeframe: str,
    requested_end: str,
    lookback_days: int,
    market_tz: str,
    session_mode: str = "rth",
    warmup_days: int = 0,
    use_sample: bool = False,
    force: bool = False,
    auto_fill_gaps: bool = True,
    allow_legacy_http_backfill: bool = False,
) -> Dict[str, str]:
    """Ensure bars via IntradayStore and write per-run snapshots + meta.

    - Intraday: uses IntradayStore.ensure (base M1) and snapshots M1/M5/M15; H1 is resampled from M1 on the fly.
    - Daily: copies cached D1 parquet into run_dir.

    Returns:
        Dict with keys: exec_path, signal_path (may be None for D1), bars_hash, meta_path
    """

    bars_dir = run_dir / "bars"
    bars_dir.mkdir(parents=True, exist_ok=True)

    tf_upper = timeframe.upper()
    if tf_upper == "D1":
        # Daily: expect cached parquet in DATA_D1
        source_path = DATA_D1 / f"{symbol}.parquet"
        if not source_path.exists():
            raise DataFetcherError(f"daily bars not found: {source_path}")
        # Snapshot into run dir
        target_exec = bars_dir / f"bars_exec_{tf_upper}.parquet"
        shutil.copyfile(source_path, target_exec)
        bars_hash = _sha256_file(source_path)
        meta = {
            "market_tz": market_tz,
            "timeframe": tf_upper,
            "warmup_days": warmup_days,
            "lookback_days": lookback_days,
            "exec_bars": target_exec.name,
            "signal_bars": None,
            "session_mode": session_mode,
            "rth_only": session_mode == "rth",
        }
        meta_path = bars_dir / "bars_slice_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        logger.info(
            "actions: pipeline_bars_snapshot_daily symbol=%s tf=%s src=%s dst=%s hash=%s",
            symbol,
            tf_upper,
            source_path,
            target_exec,
            bars_hash,
        )
        return {
            "exec_path": str(target_exec),
            "signal_path": None,
            "bars_hash": bars_hash,
            "meta_path": str(meta_path),
        }

    base_tf = tf_upper if tf_upper in {"M1", "M5", "M15"} else "M1"
    tf_enum = _resolve_timeframe(base_tf)
    end_ts = pd.Timestamp(requested_end)
    if end_ts.tz is None:
        end_ts = end_ts.tz_localize("UTC")
    else:
        end_ts = end_ts.tz_convert("UTC")
    warmup_days_calc = max(0, int((warmup_days or 0)))
    requested_start = (end_ts - pd.Timedelta(days=int(lookback_days))).normalize()
    effective_start = (requested_start - pd.Timedelta(days=warmup_days_calc)).normalize()

    # Ensure underlying data (M1 as base); resample M5/M15 handled by store.ensure
    spec = IntradaySpec(
        symbols=[symbol],
        start=effective_start.date().isoformat(),
        end=end_ts.date().isoformat(),
        timeframe=tf_enum,
        tz=market_tz,
        session_mode=session_mode,
    )

    legacy_http_backfill_allowed = (
        os.getenv("ALLOW_LEGACY_HTTP_BACKFILL") == "1"
        or bool(allow_legacy_http_backfill)
    )
    if not force:
        coverage = check_local_m1_coverage(
            symbol=symbol,
            start=effective_start.date().isoformat(),
            end=end_ts.date().isoformat(),
            tz=market_tz,
        )
        if coverage.get("has_gap") and (
            not auto_fill_gaps or not legacy_http_backfill_allowed
        ):
            hint = (
                "Backfill required (Option B): run marketdata_service.backfill_cli "
                "and ensure data exists in MARKETDATA_DATA_ROOT."
            )
            requested_range = f"{effective_start.date()}..{end_ts.date()}"
            reason = (
                "legacy_http_backfill_disabled"
                if auto_fill_gaps and not legacy_http_backfill_allowed
                else "missing historical bars"
            )
            raise MissingHistoricalDataError(
                f"{reason} for {symbol} range={requested_range}; "
                f"gaps={coverage.get('gaps', [])}. {hint}"
            )

    store = IntradayStore(default_tz=market_tz)
    actions = store.ensure(
        spec,
        force=force,
        auto_fill_gaps=auto_fill_gaps,
        allow_legacy_http_backfill=legacy_http_backfill_allowed,
        use_sample=use_sample,
    )
    logger.info(
        "actions: pipeline_intraday_ensured symbol=%s tf=%s actions=%s range=%s..%s warmup=%d",
        symbol,
        tf_upper,
        actions,
        spec.start,
        spec.end,
        warmup_days,
    )

    # Resolve source paths
    exec_source = store.path_for(symbol, timeframe=tf_enum, session_mode=session_mode)
    if not exec_source.exists():
        raise DataFetcherError(f"expected exec bars parquet missing: {exec_source}")

    # CRITICAL FIX: Load bars and filter to requested date range
    # Previously: shutil.copyfile(exec_source, target_exec) copied EVERYTHING
    # Now: Load → Filter → Save only requested range
    logger.info(
        f"actions: pipeline_loading_bars symbol={symbol} tf={tf_upper} source={exec_source}"
    )
    
    df_exec = pd.read_parquet(exec_source)
    
    # Convert to datetime index if needed
    if "timestamp" in df_exec.columns:
        df_exec = df_exec.set_index("timestamp")
    
    # Ensure timezone-aware index (SSOT: UTC)
    if df_exec.index.tz is None:
        df_exec.index = pd.to_datetime(df_exec.index, utc=True)
    else:
        df_exec.index = df_exec.index.tz_convert("UTC")

    # SSOT Snapshot Window:
    # Snapshot covers EFFECTIVE window (requested + warmup) in UTC.
    # Non-goal: no signal logic changes, only deterministic window definition.
    df_filtered = df_exec.loc[effective_start:end_ts].copy()
    
    logger.info(
        f"actions: pipeline_bars_filtered symbol={symbol} tf={tf_upper} "
        f"original_bars={len(df_exec)} filtered_bars={len(df_filtered)} "
        f"range={effective_start.date()}..{end_ts.date()} "
        f"actual_range={df_filtered.index.min().date() if not df_filtered.empty else 'N/A'}..{df_filtered.index.max().date() if not df_filtered.empty else 'N/A'}"
    )
    
    if df_filtered.empty:
        raise DataFetcherError(
            f"No bars found for {symbol} tf={tf_upper} in window "
            f"{effective_start.date()}..{end_ts.date()} "
            f"(requested_start={requested_start.date()}, warmup_days={warmup_days_calc}). "
            f"Source has {len(df_exec)} bars from {df_exec.index.min().date()} to {df_exec.index.max().date()}."
        )

    target_exec = bars_dir / f"bars_exec_{tf_upper}_rth.parquet"
    signal_target = None

    if tf_upper == "H1":
        # Resample from M1 to H1
        df_norm = _normalize_ohlcv_frame(df_filtered, target_tz=market_tz, symbol=symbol)

        agg = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        resampled = df_norm.resample("60min").agg(agg).dropna(how="any")
        if resampled.empty:
            raise DataFetcherError(f"resample to H1 produced empty frame for {symbol}")
        resampled.attrs = {}
        resampled.to_parquet(target_exec)
        signal_target = target_exec
    else:
        # Save filtered bars directly (NOT copy entire source!)
        df_filtered.to_parquet(target_exec)
        signal_target = bars_dir / f"bars_signal_{tf_upper}_rth.parquet"
        df_filtered.to_parquet(signal_target)

    bars_hash = _sha256_file(target_exec)


    meta = {
        "market_tz": market_tz,
        "timeframe": tf_upper,
        "warmup_days": warmup_days_calc,
        "lookback_days": lookback_days,
        "exec_bars": target_exec.name,
        "signal_bars": signal_target.name if signal_target else None,
        "session_mode": session_mode,
        "rth_only": session_mode == "rth",
        "actions": actions,
    }
    meta_path = bars_dir / "bars_slice_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    logger.info(
        "actions: pipeline_bars_snapshot_intraday symbol=%s tf=%s exec=%s signal=%s hash=%s",
        symbol,
        tf_upper,
        target_exec,
        signal_target,
        bars_hash,
    )

    return {
        "exec_path": str(target_exec),
        "signal_path": str(signal_target) if signal_target else None,
        "bars_hash": bars_hash,
        "meta_path": str(meta_path),
    }
