from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

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


def _load_ohlcv(path: Path, target_tz: str) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if "timestamp" in frame.columns:
        ts = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
        frame = frame.drop(columns=["timestamp"])
        frame.index = ts
    elif not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError(f"{path} is missing a datetime index or 'timestamp' column")

    if frame.index.tz is None:
        frame.index = frame.index.tz_localize("UTC")

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [col for col in required if col not in frame.columns]
    if missing:
        raise ValueError(f"{path} missing OHLCV columns: {missing}")

    ordered = frame[required].sort_index()
    ordered.index.name = "timestamp"
    if ordered.index.tz is None:
        ordered.index = ordered.index.tz_localize("UTC")
    ordered = ordered.tz_convert(target_tz)
    ordered = ordered.rename(columns=lambda c: c.lower())
    return ordered


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

    if args.session_filter:
        start_hour, end_hour = args.session_filter
        config["session_filter"] = {
            "enabled": True,
            "start_hour": start_hour,
            "end_hour": end_hour,
        }

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
    parser.add_argument("--strategy", choices=["inside_bar_v1", "inside_bar_v2"], default="inside_bar_v1")
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
    config = build_config(args)
    if args.strategy not in registry.list_strategies():
        registry.auto_discover("strategies")
    strategy = factory.create_strategy(args.strategy, config)

    rows: List[Dict[str, object]] = []

    for symbol in symbols:
        source = data_path / f"{symbol}.parquet"
        if not source.exists():
            print(f"[WARN] Missing parquet for {symbol}: {source}")
            continue

        try:
            ohlcv = _load_ohlcv(source, args.tz)
        except Exception as exc:
            print(f"[WARN] Failed to load {symbol}: {exc}")
            continue

        input_frame = ohlcv.reset_index().rename(columns={"timestamp": "timestamp"})
        signals = strategy.generate_signals(input_frame, symbol, config)

        for sig in signals:
            ts = pd.Timestamp(sig.timestamp).tz_convert(args.tz)
            session_idx = _session_id(ts, sessions)
            if session_idx == 0:
                continue

            base = {
                "ts": ts.isoformat(),
                "session_id": session_idx,
                "ib": True,
                "ib_qual": True,
                "Symbol": symbol,
                "long_entry": np.nan,
                "short_entry": np.nan,
                "sl_long": np.nan,
                "sl_short": np.nan,
                "tp_long": np.nan,
                "tp_short": np.nan,
            }

            if sig.signal_type == "LONG":
                base.update(
                    long_entry=sig.entry_price,
                    sl_long=sig.stop_loss,
                    tp_long=sig.take_profit,
                )
            elif sig.signal_type == "SHORT":
                base.update(
                    short_entry=sig.entry_price,
                    sl_short=sig.stop_loss,
                    tp_short=sig.take_profit,
                )

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
    output = Path(args.output) if args.output else SIGNALS_DIR / f"signals_ib_{timestamp}.csv"
    result.to_csv(output, index=False)

    current = Path(args.current_snapshot)
    current.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(current, index=False)

    print(f"[OK] Signals → {output} (rows={len(result)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
