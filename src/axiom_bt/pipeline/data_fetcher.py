"""Data fetcher wrapper for pipeline bars snapshots (Option B consumer-only)."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Dict

import pandas as pd

from core.settings.runtime_config import (
    RuntimeConfigError,
    get_marketdata_data_root,
)
from axiom_bt.fs import DATA_D1
from .data_prep import _sha256_file

logger = logging.getLogger(__name__)


class DataFetcherError(RuntimeError):
    """Raised when bars cannot be ensured or snapshotted."""


class MissingHistoricalDataError(DataFetcherError):
    """Raised when required historical bars are missing and producer artifacts are unavailable."""


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


def _coverage_gaps_from_bounds(
    *,
    expected_start: pd.Timestamp,
    expected_end: pd.Timestamp,
    actual_min: pd.Timestamp,
    actual_max: pd.Timestamp,
    slack_start_days: int,
    slack_end_days: int,
) -> list[dict[str, object]]:
    gaps: list[dict[str, object]] = []

    start_threshold = expected_start + pd.Timedelta(days=slack_start_days)
    end_threshold = expected_end - pd.Timedelta(days=slack_end_days)

    if actual_min > start_threshold:
        gap_start = expected_start.date()
        gap_end = (actual_min - pd.Timedelta(days=1)).date()
        if gap_end >= gap_start:
            gaps.append(
                {
                    "gap_start": gap_start.isoformat(),
                    "gap_end": gap_end.isoformat(),
                    "gap_days": (gap_end - gap_start).days + 1,
                    "reason": "before_existing_data",
                }
            )

    if actual_max < end_threshold:
        gap_start = (actual_max + pd.Timedelta(days=1)).date()
        gap_end = expected_end.date()
        if gap_end >= gap_start:
            gaps.append(
                {
                    "gap_start": gap_start.isoformat(),
                    "gap_end": gap_end.isoformat(),
                    "gap_days": (gap_end - gap_start).days + 1,
                    "reason": "after_existing_data",
                }
            )

    return gaps


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
    """Load producer-built bars and write per-run snapshots.

    Consumer-only by contract:
    - No HTTP fetch
    - No local gap/backfill logic
    - Producer must have materialized derived timeframe parquet already
    """
    del use_sample, force, auto_fill_gaps, allow_legacy_http_backfill

    bars_dir = run_dir / "bars"
    bars_dir.mkdir(parents=True, exist_ok=True)

    tf_upper = timeframe.upper()
    if tf_upper == "D1":
        source_path = DATA_D1 / f"{symbol}.parquet"
        if not source_path.exists():
            raise DataFetcherError(f"daily bars not found: {source_path}")

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
        return {
            "exec_path": str(target_exec),
            "signal_path": None,
            "bars_hash": bars_hash,
            "meta_path": str(meta_path),
        }

    tf_minutes = _timeframe_minutes(tf_upper)
    end_ts = pd.Timestamp(requested_end)
    if end_ts.tz is None:
        end_ts = end_ts.tz_localize("UTC")
    else:
        end_ts = end_ts.tz_convert("UTC")

    warmup_days_calc = max(0, int(warmup_days or 0))
    requested_start = (end_ts - pd.Timedelta(days=int(lookback_days))).normalize()
    effective_start = (requested_start - pd.Timedelta(days=warmup_days_calc)).normalize()

    try:
        md_root = get_marketdata_data_root()
    except RuntimeConfigError as exc:
        raise MissingHistoricalDataError(
            f"missing historical bars for {symbol} range={effective_start.date()}..{end_ts.date()}. "
            f"{exc}. Backfill required (Option B): run marketdata_service.backfill_cli and ensure data exists in MARKETDATA_DATA_ROOT."
        ) from exc

    derived_source = md_root / "derived" / f"tf_m{tf_minutes}" / f"{symbol.upper()}.parquet"
    if not derived_source.exists():
        raise MissingHistoricalDataError(
            f"missing historical bars for {symbol} range={effective_start.date()}..{end_ts.date()}; "
            f"derived bars missing at {derived_source}. Backfill required (Option B): "
            "run marketdata_service.backfill_cli or call producer /ensure_timeframe_bars."
        )

    logger.info("actions: pipeline_option_b_source symbol=%s source=%s", symbol, derived_source)

    df = pd.read_parquet(derived_source)
    if "ts" in df.columns:
        idx = pd.to_datetime(df["ts"], unit="s", utc=True, errors="coerce")
        df = df.drop(columns=[c for c in ["ts", "timestamp"] if c in df.columns])
        df.index = idx
    elif "timestamp" in df.columns:
        idx = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.drop(columns=["timestamp"])
        df.index = idx
    elif isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is None:
            df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
        else:
            df.index = df.index.tz_convert("UTC")
    else:
        raise DataFetcherError(f"unsupported derived schema: {derived_source}")

    df = df[~df.index.isna()].sort_index()
    df_filtered = df.loc[effective_start:end_ts].copy()
    if df_filtered.empty:
        raise MissingHistoricalDataError(
            f"missing historical bars for {symbol} range={effective_start.date()}..{end_ts.date()}. "
            "Backfill required (Option B): run marketdata_service.backfill_cli or call producer /ensure_timeframe_bars."
        )

    actual_min = df_filtered.index.min()
    actual_max = df_filtered.index.max()
    gaps = _coverage_gaps_from_bounds(
        expected_start=effective_start,
        expected_end=end_ts,
        actual_min=actual_min,
        actual_max=actual_max,
        slack_start_days=7,
        slack_end_days=2,
    )
    coverage_ok = not gaps
    logger.info(
        "actions: derived_timeframe_coverage_check symbol=%s tf_m=%s expected_start=%s expected_end=%s "
        "actual_min=%s actual_max=%s slack_start_days=%s slack_end_days=%s coverage_ok=%s",
        symbol,
        tf_minutes,
        effective_start.isoformat(),
        end_ts.isoformat(),
        actual_min.isoformat(),
        actual_max.isoformat(),
        7,
        2,
        coverage_ok,
    )
    if not coverage_ok:
        raise MissingHistoricalDataError(
            f"insufficient_derived_coverage for {symbol} tf={tf_upper} range={effective_start.date()}..{end_ts.date()}; "
            f"gaps={gaps}. Backfill required (Option B): run marketdata_service.backfill_cli or call producer /ensure_timeframe_bars."
        )

    target_exec = bars_dir / f"bars_exec_{tf_upper}_rth.parquet"
    signal_target = target_exec if tf_upper in {"M1", "H1"} else bars_dir / f"bars_signal_{tf_upper}_rth.parquet"
    df_filtered.to_parquet(target_exec)
    if signal_target != target_exec:
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
        "option_b_source": str(derived_source),
        "consumer_only": True,
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
