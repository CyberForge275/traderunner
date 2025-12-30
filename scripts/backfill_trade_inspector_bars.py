#!/usr/bin/env python3
"""
Backfill Trade Inspector Bars
==============================

Regenerates bars/ directories for existing backtest runs so that the
Trade Inspector can display charts.

This script:
1. Scans existing backtest runs in artifacts/backtests/
2. For each run with trades.csv but missing bars/
3. Loads the bar data from IntradayStore
4. Saves to bars/ subdirectory in the correct format

Usage:
    python scripts/backfill_trade_inspector_bars.py --all
    python scripts/backfill_trade_inspector_bars.py --run 251222_110818_IONQ_NEW1_IB_100d
    python scripts/backfill_trade_inspector_bars.py --top 10
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from axiom_bt.intraday import IntradayStore, Timeframe

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_bars(run_dir: Path, force: bool = False) -> bool:
    """Regenerate bars for a specific backtest run.

    Args:
        run_dir: Path to the run directory
        force: If True, overwrite existing bars/

    Returns:
        True if successful, False otherwise
    """
    run_id = run_dir.name

    # Check if trades.csv exists
    if not (run_dir / "trades.csv").exists():
        logger.debug(f"[{run_id}] No trades.csv, skipping")
        return False

    # Check if bars/ already exists
    bars_dir = run_dir / "bars"
    if bars_dir.exists() and not force:
        existing_parquets = list(bars_dir.glob("*.parquet"))
        if existing_parquets:
            logger.info(f"[{run_id}] ✓ Already has bars/ with {len(existing_parquets)} files, skipping")
            return True

    # Load run metadata
    meta_path = run_dir / "run_meta.json"
    if not meta_path.exists():
        logger.warning(f"[{run_id}] ❌ No run_meta.json, skipping")
        return False

    try:
        meta = json.loads(meta_path.read_text())
        symbol = meta["data"]["symbols"][0]
        timeframe = meta["data"]["timeframe"]
        market_tz = meta.get("market_tz", "America/New_York")

        logger.info(f"[{run_id}] Loading {symbol} {timeframe} bars...")

        # Load bars from IntradayStore
        store = IntradayStore(default_tz=market_tz)
        tf_enum = Timeframe[timeframe.upper()]
        bars = store.load(symbol, timeframe=tf_enum, tz=market_tz)

        if bars is None or bars.empty:
            logger.warning(f"[{run_id}] ❌ No bars loaded from IntradayStore")
            return False

        # Create bars/ directory
        bars_dir.mkdir(exist_ok=True)

        # Remove .attrs to avoid JSON serialization issues
        bars_clean = bars.copy()
        bars_clean.attrs = {}

        # Save both exec and signal bars (same data for backfill)
        exec_path = bars_dir / f"bars_exec_{timeframe.upper()}_rth.parquet"
        signal_path = bars_dir / f"bars_signal_{timeframe.upper()}_rth.parquet"

        bars_clean.to_parquet(exec_path)
        bars_clean.to_parquet(signal_path)

        # Write metadata
        meta_data = {
            "market_tz": market_tz,
            "timeframe": timeframe,
            "exec_bars": f"bars_exec_{timeframe.upper()}_rth.parquet",
            "signal_bars": f"bars_signal_{timeframe.upper()}_rth.parquet",
            "rth_only": True,
            "backfilled": True,
        }
        (bars_dir / "bars_slice_meta.json").write_text(json.dumps(meta_data, indent=2))

        logger.info(f"[{run_id}] ✅ Backfilled {len(bars)} bars → {exec_path.name}, {signal_path.name}")
        return True

    except Exception as e:
        logger.error(f"[{run_id}] ❌ Failed to backfill: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(description="Backfill Trade Inspector bars for existing backtest runs")
    parser.add_argument("--all", action="store_true", help="Backfill all runs")
    parser.add_argument("--run", type=str, help="Backfill specific run by ID")
    parser.add_argument("--top", type=int, help="Backfill top N most recent runs")
    parser.add_argument("--force", action="store_true", help="Overwrite existing bars/")
    parser.add_argument("--artifacts-root", type=str, default="artifacts/backtests",
                        help="Path to artifacts root (default: artifacts/backtests)")

    args = parser.parse_args()

    artifacts_root = Path(args.artifacts_root)
    if not artifacts_root.exists():
        logger.error(f"❌ Artifacts root not found: {artifacts_root}")
        return 1

    # Determine which runs to process
    if args.run:
        run_dirs = [artifacts_root / args.run]
        if not run_dirs[0].exists():
            logger.error(f"❌ Run not found: {args.run}")
            return 1
    elif args.all:
        run_dirs = sorted(artifacts_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    elif args.top:
        run_dirs = sorted(artifacts_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:args.top]
    else:
        parser.print_help()
        return 1

    # Filter to directories only
    run_dirs = [d for d in run_dirs if d.is_dir()]

    logger.info(f"Processing {len(run_dirs)} runs...")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for run_dir in run_dirs:
        result = backfill_bars(run_dir, force=args.force)
        if result is True:
            success_count += 1
        elif result is False:
            fail_count += 1
        else:
            skip_count += 1

    logger.info(f"\n{'='*60}")
    logger.info(f"BACKFILL COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Success: {success_count}")
    logger.info(f"❌ Failed: {fail_count}")
    logger.info(f"⏭️  Skipped: {skip_count}")
    logger.info(f"{'='*60}")

    return 0


if __name__ == "__main__":
    exit(main())
