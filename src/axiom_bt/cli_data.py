from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import time
from pathlib import Path
from typing import List

from axiom_bt.fs import (
    DATA_D1,
    DATA_M1,
    DATA_M15,
    DATA_M5,
    ensure_layout,
)
from axiom_bt.data.eodhd_fetch import (
    fetch_eod_daily_to_parquet,
    fetch_intraday_1m_to_parquet,
    resample_m1,
)


def _parse_symbols(symbols: str | None, universe_file: str | None) -> List[str]:
    if symbols:
        return [s.strip().upper() for s in symbols.split(",") if s.strip()]

    if universe_file:
        path = Path(universe_file)
        if not path.exists():
            raise SystemExit(f"Universe file not found: {path}")
        import pandas as pd

        data = pd.read_csv(path)
        column = "Symbol" if "Symbol" in data.columns else data.columns[0]
        return data[column].astype(str).str.strip().str.upper().tolist()

    raise SystemExit("Provide --symbols or --universe-file")


def cmd_ensure_intraday(args: argparse.Namespace) -> int:
    ensure_layout()
    symbols = _parse_symbols(args.symbols, args.universe_file)
    now = datetime.now(timezone.utc)
    start = args.start or (now - timedelta(days=2)).date().isoformat()
    end = args.end or now.date().isoformat()

    overall_start = time.perf_counter()
    for symbol in symbols:
        symbol_start = time.perf_counter()
        fetch_duration = None
        resample_m5_duration = None
        resample_m15_duration = None
        m1_path = DATA_M1 / f"{symbol}.parquet"
        if args.force or not m1_path.exists():
            print(f"[FETCH] {symbol} M1 {start}..{end}")
            fetch_start = time.perf_counter()
            try:
                fetch_intraday_1m_to_parquet(
                    symbol,
                    args.exchange,
                    start,
                    end,
                    DATA_M1,
                    tz=args.tz,
                    use_sample=args.use_sample,
                )
                fetch_duration = time.perf_counter() - fetch_start
            except Exception as exc:  # tolerant for symbols with no data
                msg = str(exc)
                # EODHD may legitimately return "No data" for some
                # symbols/windows; log and continue instead of failing
                # the entire batch.
                if "No data from EODHD" in msg or "No data" in msg:
                    print(f"[WARN] Skipping {symbol}: {msg}")
                    continue
                raise
        else:
            print(f"[SKIP] {symbol} M1 exists: {m1_path}")

        print(f"[RESAMPLE] {symbol} -> M5")
        resample_m5_start = time.perf_counter()
        resample_m1(m1_path, DATA_M5, interval="5min", tz=args.tz)
        resample_m5_duration = time.perf_counter() - resample_m5_start

        if args.generate_m15:
            print(f"[RESAMPLE] {symbol} -> M15")
            resample_m15_start = time.perf_counter()
            resample_m1(m1_path, DATA_M15, interval="15min", tz=args.tz)
            resample_m15_duration = time.perf_counter() - resample_m15_start

        symbol_total = time.perf_counter() - symbol_start
        parts = [f"total={symbol_total:.2f}s"]
        if fetch_duration is not None:
            parts.append(f"fetch={fetch_duration:.2f}s")
        if resample_m5_duration is not None:
            parts.append(f"resample_m5={resample_m5_duration:.2f}s")
        if resample_m15_duration is not None:
            parts.append(f"resample_m15={resample_m15_duration:.2f}s")
        print(f"[TIMING] {symbol} " + ", ".join(parts))

    total_elapsed = time.perf_counter() - overall_start
    print(f"[DONE] ensure-intraday total={total_elapsed:.2f}s symbols={len(symbols)}")
    return 0


def cmd_fetch_daily(args: argparse.Namespace) -> int:
    ensure_layout()
    symbols = _parse_symbols(args.symbols, args.universe_file)
    now = datetime.now(timezone.utc)
    start = args.start or (now - timedelta(days=120)).date().isoformat()
    end = args.end or now.date().isoformat()

    for symbol in symbols:
        print(f"[FETCH D1] {symbol} {start}..{end}")
        fetch_eod_daily_to_parquet(
            symbol,
            args.exchange,
            start,
            end,
            DATA_D1,
            tz=args.tz,
            use_sample=args.use_sample,
        )

    print("[DONE] fetch-d1")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="axiom_bt.cli_data", description="EODHD data utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_intraday = sub.add_parser("ensure-intraday", help="Fetch M1 intraday data and resample to M5/M15")
    p_intraday.add_argument("--symbols", help="Comma-separated symbols")
    p_intraday.add_argument("--universe-file", help="CSV with symbol column")
    p_intraday.add_argument("--exchange", default="US")
    p_intraday.add_argument("--tz", default="Europe/Berlin")
    p_intraday.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    p_intraday.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    p_intraday.add_argument("--force", action="store_true", help="Refetch existing M1 files")
    p_intraday.add_argument("--generate-m15", action="store_true", help="Resample to M15 in addition to M5")
    p_intraday.add_argument("--use-sample", action="store_true", help="Use synthetic data instead of live fetch")
    p_intraday.set_defaults(func=cmd_ensure_intraday)

    p_daily = sub.add_parser("fetch-d1", help="Fetch end-of-day data")
    p_daily.add_argument("--symbols", help="Comma-separated symbols")
    p_daily.add_argument("--universe-file", help="CSV with symbol column")
    p_daily.add_argument("--exchange", default="US")
    p_daily.add_argument("--tz", default="America/New_York")
    p_daily.add_argument("--start", default=None)
    p_daily.add_argument("--end", default=None)
    p_daily.add_argument("--use-sample", action="store_true", help="Use synthetic data instead of live fetch")
    p_daily.set_defaults(func=cmd_fetch_daily)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
