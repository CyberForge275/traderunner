"""CLI entry for the modular pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .runner import run_pipeline
from .strategy_config_loader import load_strategy_params_from_ssot


def build_parser() -> argparse.ArgumentParser:
    """Define CLI arguments for the headless pipeline.

    Required: strategy id/version, symbol, timeframe, output dir, bars path,
    and either (valid_to/requested_end + lookback_days) or valid_from+valid_to.
    """
    p = argparse.ArgumentParser(description="Axiom BT modular pipeline (CLI)")
    p.add_argument("--run-id", required=True)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--bars-path", required=True, type=Path)
    p.add_argument("--strategy-id", required=True)
    p.add_argument("--strategy-version", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", required=True)
    p.add_argument("--requested-end", required=False, help="End date (ISO) for data window (alias: --valid-to)")
    p.add_argument("--valid-to", required=False, help="End date (ISO) for data window (alias of --requested-end)")
    p.add_argument("--valid-from", required=False, help="Start date (ISO); if provided, lookback-days is derived")
    p.add_argument("--lookback-days", required=False, type=int, help="Lookback days (without warmup)")
    p.add_argument("--valid-from-policy", required=False, choices=["signal_ts", "next_bar"])
    p.add_argument("--order-validity-policy", required=False, choices=["session_end", "fixed_minutes", "one_bar"])
    p.add_argument("--compound-enabled", action="store_true")
    p.add_argument("--compound-equity-basis", default="cash_only")
    p.add_argument("--initial-cash", type=float, default=10000.0)
    p.add_argument("--fees-bps", type=float, default=1.0)
    p.add_argument("--slippage-bps", type=float, default=0.25)
    return p


def main(argv=None) -> int:
    """CLI entry: parse args, load SSOT config, and delegate to run_pipeline."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)

    requested_end = args.requested_end or args.valid_to
    if not requested_end:
        raise SystemExit("--requested-end or --valid-to is required")

    lookback_days = args.lookback_days
    if lookback_days is None and args.valid_from:
        from datetime import date

        try:
            start = date.fromisoformat(args.valid_from)
            end = date.fromisoformat(requested_end)
        except Exception as exc:  # pragma: no cover
            raise SystemExit(f"invalid date format: {exc}") from exc
        delta = (end - start).days
        if delta <= 0:
            raise SystemExit("valid_from must be before valid_to/requested_end")
        lookback_days = delta

    if lookback_days is None:
        raise SystemExit("--lookback-days or --valid-from must be provided")

    cfg = load_strategy_params_from_ssot(args.strategy_id, args.strategy_version)
    params = {
        **cfg.get("core", {}),
        **cfg.get("tunable", {}),
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "requested_end": requested_end,
        "lookback_days": lookback_days,
    }
    if args.valid_from_policy:
        params["valid_from_policy"] = args.valid_from_policy
    if args.order_validity_policy:
        params["order_validity_policy"] = args.order_validity_policy
    run_pipeline(
        run_id=args.run_id,
        out_dir=args.out_dir,
        bars_path=args.bars_path,
        strategy_id=args.strategy_id,
        strategy_version=args.strategy_version,
        strategy_params=params,
        strategy_meta=cfg,
        compound_enabled=args.compound_enabled,
        compound_equity_basis=args.compound_equity_basis,
        initial_cash=args.initial_cash,
        fees_bps=args.fees_bps,
        slippage_bps=args.slippage_bps,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
