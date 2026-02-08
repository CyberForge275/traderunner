"""Offline smoke runner for pipeline (no network)."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from axiom_bt.pipeline.runner import run_pipeline
from axiom_bt.pipeline.strategy_config_loader import load_strategy_params_from_ssot


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Axiom BT offline smoke runner")
    p.add_argument("--run-id", required=True)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--bars-path", required=True, type=Path)
    p.add_argument("--strategy-id", required=True)
    p.add_argument("--strategy-version", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", required=True)
    p.add_argument("--requested-end", required=True)
    p.add_argument("--lookback-days", required=True, type=int)
    return p


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)

    os.environ.setdefault("EODHD_OFFLINE", "1")
    if not args.bars_path.exists():
        raise SystemExit(f"bars-path missing: {args.bars_path}")

    cfg = load_strategy_params_from_ssot(args.strategy_id, args.strategy_version)
    params = {
        **cfg.get("core", {}),
        **cfg.get("tunable", {}),
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "requested_end": args.requested_end,
        "lookback_days": args.lookback_days,
    }

    run_pipeline(
        run_id=args.run_id,
        out_dir=args.out_dir,
        bars_path=args.bars_path,
        strategy_id=args.strategy_id,
        strategy_version=args.strategy_version,
        strategy_params=params,
        strategy_meta=cfg,
        compound_enabled=False,
        compound_equity_basis="cash_only",
        initial_cash=10000.0,
        fees_bps=1.0,
        slippage_bps=0.25,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
