from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from axiom_bt.intraday import IntradayStore, Timeframe
from axiom_bt.contracts.signal_schema import SignalOutputSpec
from strategies import factory, registry
from core.settings import (
    INSIDE_BAR_SESSIONS,
    INSIDE_BAR_TIMEZONE,
)


SIGNALS_DIR = Path("artifacts/signals")
BERLIN_TZ = INSIDE_BAR_TIMEZONE


def _parse_sessions(raw: str) -> List[Tuple[time, time]]:
    windows: List[Tuple[time, time]] = []
    for chunk in [part.strip() for part in raw.split(",") if part.strip()]:
        start, end = chunk.split("-")
        h1, m1 = map(int, start.split(":"))
        h2, m2 = map(int, end.split(":"))
        windows.append((time(h1, m1), time(h2, m2)))
    return windows


def _infer_symbols(data_path: Path) -> List[str]:
    return sorted({p.stem.upper() for p in data_path.glob("*.parquet")})


def _session_id(ts: pd.Timestamp, sessions: List[Tuple[time, time]]) -> int:
    if not sessions:
        return 0
    local_ts = ts
    for idx, (start, end) in enumerate(sessions, start=1):
        tt = local_ts.time()
        if start <= tt < end:
            return idx
    return 0


def build_config(args: argparse.Namespace) -> Dict[str, object]:
    config: Dict[str, object] = {
        "atr_period": args.atr_period,
        "risk_reward_ratio": args.rrr,
        "inside_bar_mode": args.ib_mode,
        "min_mother_bar_size": args.min_master_body,
        "breakout_confirmation": not args.allow_touch_breakout,
    }

    if args.max_master_atr_mult is not None:
        config["max_master_range_atr_mult"] = args.max_master_atr_mult

    config["min_master_body_ratio"] = args.min_master_body_ratio
    config["execution_lag_bars"] = max(0, int(args.execution_lag))

    if args.stop_cap is not None and args.stop_cap > 0:
        config["stop_distance_cap"] = float(args.stop_cap)

    # NEW: Build SessionFilter from --sessions argument
    # This replaces the old session filtering logic in main()
    if args.sessions:
        from strategies.inside_bar.config import SessionFilter
        session_strings = [s.strip() for s in args.sessions.split(",") if s.strip()]
        if session_strings:
            session_filter = SessionFilter.from_strings(session_strings)
            config["session_filter"] = session_filter

    return config


def _aggregate_rows(rows: List[Dict[str, object]]) -> pd.DataFrame:
    if not rows:
        columns = [
            "ts",
            "session_id",
            "ib",
            "ib_qual",
            "long_entry",
            "short_entry",
            "sl_long",
            "sl_short",
            "tp_long",
            "tp_short",
            "Symbol",
            "strategy",
            "strategy_version",
        ]
        return pd.DataFrame(columns=columns)

    frame = pd.DataFrame(rows)
    key_cols = ["ts", "Symbol", "session_id"]

    frame.set_index(key_cols, inplace=True)
    merged = frame.groupby(level=key_cols, sort=True).agg(
        {
            "ib": "max",
            "ib_qual": "max",
            "long_entry": "first",
            "short_entry": "first",
            "sl_long": "first",
            "sl_short": "first",
            "tp_long": "first",
            "tp_short": "first",
            "strategy": "first",
            "strategy_version": "first",
        }
    )
    merged.reset_index(inplace=True)
    merged.sort_values(["ts", "Symbol"], inplace=True)
    return merged


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate inside-bar signals from parquet OHLCV data")
    parser.add_argument("--symbols", help="Comma-separated symbols; defaults to all files in --data-path")
    parser.add_argument("--data-path", default="artifacts/data_m5")
    parser.add_argument("--tz", default=BERLIN_TZ)
    parser.add_argument("--sessions", default=",".join(INSIDE_BAR_SESSIONS))
    parser.add_argument("--trade-type", choices=["LONG", "SHORT", "BOTH"], default="BOTH")
    parser.add_argument("--ib-mode", choices=["inclusive", "strict"], default="inclusive")
    parser.add_argument("--min-master-body", type=float, default=0.5)
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--rrr", type=float, default=1.0)
    parser.add_argument("--allow-touch-breakout", action="store_true", help="Allow breakouts on wick touch (disables close confirmation)")
    parser.add_argument("--session-filter", type=int, nargs=2, metavar=("START", "END"), help="Optional inclusive hour range for session filter")
    parser.add_argument("--strategy", choices=["inside_bar", "inside_bar_v2"], default="inside_bar")
    parser.add_argument("--max-master-atr-mult", type=float, default=None, help="Suppress signals if master range exceeds this multiple of ATR (v2)")
    parser.add_argument("--min-master-body-ratio", type=float, default=0.5, help="Minimum master candle body ratio (v2)")
    parser.add_argument("--execution-lag", type=int, default=0, help="Execution lag in bars before arming breakout orders (v2)")
    parser.add_argument("--stop-cap", type=float, default=None, help="Maximum stop distance; target retargeted to maintain RRR (v2)")
    parser.add_argument("--current-snapshot", default=str(SIGNALS_DIR / "current_signals_ib.csv"), help="Path for latest snapshot CSV")
    parser.add_argument("--output", default=None, help="Optional explicit output path")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    data_path = Path(args.data_path)
    data_path.mkdir(parents=True, exist_ok=True)

    if args.symbols:
        symbols = [sym.strip().upper() for sym in args.symbols.split(",") if sym.strip()]
    else:
        symbols = _infer_symbols(data_path)

    if not symbols:
        print("[WARN] No symbols discovered under", data_path)
        return 0

    sessions = _parse_sessions(args.sessions)
    store = IntradayStore(default_tz=args.tz)
    config = build_config(args)
    if args.strategy not in registry.list_strategies():
        registry.auto_discover("strategies")
    strategy = factory.create_strategy(args.strategy, config)

    # Import per-strategy version metadata so inside_bar and inside_bar_v2
    # can evolve independently.
    from decimal import Decimal
    try:
        from strategies.inside_bar.core import STRATEGY_VERSION as IB_VERSION
    except Exception:  # pragma: no cover - defensive fallback
        IB_VERSION = "unknown"

    try:
        from strategies.inside_bar_v2.strategy import STRATEGY_VERSION_V2
    except Exception:  # pragma: no cover - defensive fallback
        STRATEGY_VERSION_V2 = "unknown"

    rows: List[Dict[str, object]] = []
    failed_symbols = []  # Track symbols with data issues
    missing_symbols = []  # Track symbols with no data files

    for symbol in symbols:
        try:
            ohlcv = store.load(symbol, timeframe=Timeframe.M5, tz=args.tz)
        except FileNotFoundError:
            source = data_path / f"{symbol}.parquet"
            print(f"[ERROR] Missing data file for {symbol}: {source}")
            print(f"        This symbol was requested but no parquet file exists.")
            missing_symbols.append(symbol)
            continue
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[ERROR] Failed to load {symbol}: {type(exc).__name__}: {exc}")
            failed_symbols.append(f"{symbol} ({type(exc).__name__})")
            continue

        # ENHANCED: Validate data quality before processing
        if ohlcv.empty:
            print(f"[ERROR] {symbol}: Loaded data is empty (0 rows)")
            print(f"        This indicates the parquet file exists but contains no data.")
            failed_symbols.append(f"{symbol} (empty data)")
            continue
        
        # Check for NaN values in critical columns
        nan_cols = []
        for col in ['open', 'high', 'low', 'close']:
            if col in ohlcv.columns and ohlcv[col].isna().any():
                nan_count = ohlcv[col].isna().sum()
                nan_cols.append(f"{col}({nan_count} NaN)")
        
        if nan_cols:
            print(f"[ERROR] {symbol}: Data contains NaN values in OHLC columns")
            print(f"        Affected columns: {', '.join(nan_cols)}")
            print(f"        Total rows: {len(ohlcv)}, Date range: {ohlcv.index[0]} to {ohlcv.index[-1]}")
            print(f"        This violates data quality SLA 'no_nan_ohlc'.")
            failed_symbols.append(f"{symbol} (NaN in {', '.join(nan_cols)})")
            continue

        input_frame = ohlcv.reset_index().rename(columns={"timestamp": "timestamp"})
        signals = strategy.generate_signals(input_frame, symbol, config)

        for sig in signals:
            ts = pd.Timestamp(sig.timestamp).tz_convert(args.tz)
            
            # Calculate session ID for grouping (still needed for deduplication)
            session_idx = _session_id(ts, sessions)
            
            # NOTE: Session filtering is now handled by strategy.generate_signals()
            # via config.session_filter parameter. The old "if session_idx == 0: continue"
            # logic has been removed to avoid double-filtering.

            # Determine entries
            long_entry = None
            short_entry = None
            sl_long = None
            sl_short = None  # FIX: Must initialize before conditional assignment
            tp_long = None
            tp_short = None  # FIX: Must initialize before conditional assignment

            if sig.signal_type == "LONG":
                long_entry = sig.entry_price
                sl_long = sig.stop_loss
                tp_long = sig.take_profit
            elif sig.signal_type == "SHORT":
                short_entry = sig.entry_price
                sl_short = sig.stop_loss
                tp_short = sig.take_profit

            # Select correct version per strategy
            if args.strategy == "inside_bar_v2":
                strategy_version = STRATEGY_VERSION_V2
            else:
                strategy_version = IB_VERSION

            # Validate and normalize via SignalOutputSpec (ensures canonical schema)
            spec = SignalOutputSpec(
                symbol=symbol,
                timestamp=ts.tz_convert("UTC"),
                strategy=args.strategy,
                strategy_version=strategy_version,
                long_entry=Decimal(str(long_entry)) if long_entry is not None else None,
                short_entry=Decimal(str(short_entry)) if short_entry is not None else None,
                sl_long=Decimal(str(sl_long)) if sl_long is not None else None,
                sl_short=Decimal(str(sl_short)) if sl_short is not None else None,
                tp_long=Decimal(str(tp_long)) if tp_long is not None else None,
                tp_short=Decimal(str(tp_short)) if tp_short is not None else None,
                setup="inside_bar",
                score=1.0,
                metadata=sig.metadata,
            )

            base = {
                "ts": ts.isoformat(),
                "session_id": session_idx,
                "ib": True,
                "ib_qual": True,
                "Symbol": spec.symbol,
                "long_entry": float(spec.long_entry) if spec.long_entry else np.nan,
                "short_entry": float(spec.short_entry) if spec.short_entry else np.nan,
                "sl_long": float(spec.sl_long) if spec.sl_long else np.nan,
                "sl_short": float(spec.sl_short) if spec.sl_short else np.nan,
                "tp_long": float(spec.tp_long) if spec.tp_long else np.nan,
                "tp_short": float(spec.tp_short) if spec.tp_short else np.nan,
                "strategy": spec.strategy,
                "strategy_version": spec.strategy_version,
            }

            rows.append(base)

    result = _aggregate_rows(rows)
    result = result[
        [
            "ts",
            "session_id",
            "ib",
            "ib_qual",
            "long_entry",
            "short_entry",
            "sl_long",
            "sl_short",
            "tp_long",
            "tp_short",
            "Symbol",
            "strategy",
            "strategy_version",
        ]
    ]
    if not result.empty:
        result["ib"] = result["ib"].astype(bool)
        result["ib_qual"] = result["ib_qual"].astype(bool)
        ts_local = pd.to_datetime(result["ts"], utc=True).dt.tz_convert(args.tz)
        result["_session_date"] = ts_local.dt.date
        result["_rank"] = (
            result.groupby(["Symbol", "_session_date", "session_id"])  # type: ignore
            .cumcount()
            + 1
        )
        result = result[result["_rank"] == 1].drop(columns=["_session_date", "_rank"])

    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")

    # Full output (includes strategy + strategy_version for downstream
    # metadata-aware consumers and validation tests).
    output = Path(args.output) if args.output else SIGNALS_DIR / f"signals_ib_{timestamp}.csv"
    result.to_csv(output, index=False)

    # Current snapshot used by legacy pipelines expects the original
    # column contract without strategy metadata. Trim to the legacy
    # schema to keep existing tests and consumers stable.
    snapshot_cols = [
        "ts",
        "session_id",
        "ib",
        "ib_qual",
        "long_entry",
        "short_entry",
        "sl_long",
        "sl_short",
        "tp_long",
        "tp_short",
        "Symbol",
    ]
    snapshot_df = result[snapshot_cols] if not result.empty else result[snapshot_cols]

    current = Path(args.current_snapshot)
    current.parent.mkdir(parents=True, exist_ok=True)
    snapshot_df.to_csv(current, index=False)

    # ENHANCED: Report data issues and exit with appropriate codes
    total_requested = len(symbols)
    total_failed = len(failed_symbols) + len(missing_symbols)
    total_processed = total_requested - total_failed
    
    print(f"[OK] Signals → {output} (rows={len(result)})")
    print(f"[INFO] Processed {total_processed}/{total_requested} symbols")
    
    if missing_symbols:
        print(f"[ERROR] {len(missing_symbols)} symbol(s) had missing data files:")
        for sym in missing_symbols[:5]:  # Show first 5
            print(f"        - {sym}")
        if len(missing_symbols) > 5:
            print(f"        ... and {len(missing_symbols) - 5} more")
    
    if failed_symbols:
        print(f"[ERROR] {len(failed_symbols)} symbol(s) had invalid data:")
        for sym in failed_symbols[:5]:  # Show first 5
            print(f"        - {sym}")
        if len(failed_symbols) > 5:
            print(f"        ... and {len(failed_symbols) - 5} more")
    
    # Exit codes:
    # 0 = Success (no errors)
    # 1 = All symbols missing/failed (complete failure)
    # 2 = Some symbols failed but some succeeded (partial success)
    if total_processed == 0:
        print("[FATAL] No symbols could be processed. Check data availability.")
        return 1  # Complete failure
    elif total_failed > 0:
        print(f"[WARN] Partial success: {total_failed} symbol(s) failed but {total_processed} succeeded.")
        # Still return 0 for partial success to allow pipeline to continue
        # Logging will show which symbols failed
        return 0
    else:
        return 0  # Complete success


if __name__ == "__main__":
    raise SystemExit(main())
