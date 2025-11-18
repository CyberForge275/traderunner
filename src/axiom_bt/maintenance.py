from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

from axiom_bt.fs import BACKTESTS, DATA_M1, DATA_M15, DATA_M5, ensure_layout


ORDERS_DIR = Path("artifacts") / "orders"


def _normalize_path(value: Optional[Path | str], fallback: Path) -> Path:
    if value is None:
        return fallback
    return Path(value)


def _sorted_by_mtime(paths: Iterable[Path], reverse: bool = True) -> List[Path]:
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=reverse)


def cleanup_backtests(
    retain: int = 5,
    older_than_days: Optional[int] = None,
    dry_run: bool = False,
    backtests_dir: Optional[Path | str] = None,
) -> List[Path]:
    """Remove backtest run directories beyond retention policy."""

    ensure_layout()
    directory = _normalize_path(backtests_dir, BACKTESTS)
    if not directory.exists():
        return []

    runs = [p for p in directory.glob("run_*") if p.is_dir()]
    if not runs:
        return []

    runs_sorted = _sorted_by_mtime(runs)
    keep_count = max(retain, 0)
    keep_set = set(runs_sorted[:keep_count])
    candidates = [p for p in runs_sorted if p not in keep_set]

    cutoff = None
    if older_than_days is not None:
        cutoff = datetime.now() - timedelta(days=max(older_than_days, 0))

    to_delete: List[Path] = []
    for path in candidates:
        if cutoff is not None:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if mtime >= cutoff:
                continue
        to_delete.append(path)

    if not dry_run:
        for path in to_delete:
            shutil.rmtree(path, ignore_errors=True)

    return to_delete


def cleanup_orders(
    retain: int = 5,
    dry_run: bool = False,
    orders_dir: Optional[Path | str] = None,
) -> List[Path]:
    """Remove historical order CSV files beyond retention policy."""

    directory = _normalize_path(orders_dir, ORDERS_DIR)
    if not directory.exists():
        return []

    csv_files = [p for p in directory.glob("orders_*.csv") if p.is_file()]
    csv_files = [p for p in csv_files if p.name != "current_orders.csv"]
    if not csv_files:
        return []

    files_sorted = _sorted_by_mtime(csv_files)
    keep_count = max(retain, 0)
    keep_set = set(files_sorted[:keep_count])
    to_delete = [p for p in files_sorted if p not in keep_set]

    if not dry_run:
        for path in to_delete:
            path.unlink(missing_ok=True)

    return to_delete


DATA_TIMEFRAMES = {
    "M1": DATA_M1,
    "M5": DATA_M5,
    "M15": DATA_M15,
}


def cleanup_data(
    timeframe: str,
    keep_symbols: Optional[Iterable[str]] = None,
    dry_run: bool = False,
    data_dir: Optional[Path | str] = None,
) -> List[Path]:
    """Delete cached data files not referenced in keep_symbols."""

    tf = timeframe.upper()
    base_dir = _normalize_path(data_dir, DATA_TIMEFRAMES.get(tf, DATA_M5))
    if not base_dir.exists() or keep_symbols is None:
        return []

    keep: Set[str] = {symbol.strip().upper() for symbol in keep_symbols if symbol.strip()}
    if not keep:
        return []

    to_delete: List[Path] = []
    for parquet in base_dir.glob("*.parquet"):
        if parquet.stem.upper() not in keep:
            to_delete.append(parquet)

    if not dry_run:
        for path in to_delete:
            path.unlink(missing_ok=True)

    return to_delete


@dataclass
class CleanupReport:
    removed_runs: List[Path]
    removed_orders: List[Path]
    removed_data: List[Path]


def cleanup_artifacts(
    retain_runs: int = 5,
    retain_orders: int = 5,
    keep_symbols: Optional[Sequence[str]] = None,
    data_timeframe: str = "M5",
    older_than_days: Optional[int] = None,
    dry_run: bool = False,
    backtests_dir: Optional[Path | str] = None,
    orders_dir: Optional[Path | str] = None,
    data_dir: Optional[Path | str] = None,
) -> CleanupReport:
    """Convenience wrapper to apply all cleanup routines."""

    removed_runs = cleanup_backtests(retain_runs, older_than_days, dry_run, backtests_dir=backtests_dir)
    removed_orders = cleanup_orders(retain_orders, dry_run, orders_dir=orders_dir)
    removed_data = cleanup_data(data_timeframe, keep_symbols, dry_run, data_dir=data_dir)
    return CleanupReport(removed_runs, removed_orders, removed_data)


def parse_list(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean up TradeRunner artifacts")
    parser.add_argument("--retain-runs", type=int, default=5, help="Number of recent backtest runs to keep")
    parser.add_argument("--retain-orders", type=int, default=5, help="Number of recent orders CSV files to keep")
    parser.add_argument(
        "--keep-symbols",
        type=str,
        default="",
        help="Comma-separated symbols to keep in cache (others will be deleted)",
    )
    parser.add_argument(
        "--data-timeframe",
        type=str,
        default="M5",
        choices=list(DATA_TIMEFRAMES.keys()),
        help="Data timeframe cache to prune",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=None,
        help="Only delete runs older than this many days",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report deletions without removing files")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    keep_symbols = parse_list(args.keep_symbols)

    report = cleanup_artifacts(
        retain_runs=args.retain_runs,
        retain_orders=args.retain_orders,
        keep_symbols=keep_symbols,
        data_timeframe=args.data_timeframe,
        older_than_days=args.older_than_days,
        dry_run=args.dry_run,
    )

    def fmt(paths: List[Path]) -> str:
        return ", ".join(str(p) for p in paths) if paths else "(none)"

    print("Runs removed:", fmt(report.removed_runs))
    print("Orders removed:", fmt(report.removed_orders))
    print("Data removed:", fmt(report.removed_data))
    if args.dry_run:
        print("Dry run complete - no files deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
