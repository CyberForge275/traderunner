#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 12 22:19:59 2026

@author: mirko
"""

# run_pipeline_spyder.py
import os
import sys
from pathlib import Path
from datetime import datetime

# Ensure local source takes precedence (avoid stale installed package)
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axiom_bt.pipeline.runner import run_pipeline
from axiom_bt.pipeline.paths import get_backtest_run_dir
from axiom_bt.pipeline.strategy_config_loader import load_strategy_params_from_ssot

if __name__ == "__main__":
    ts = datetime.now().strftime("%y%m%d_%H%M%S")
    strategy_id = "insidebar_intraday"
    strategy_version = "1.0.1"
    requested_end = "2026-02-06"
    consumer_only = os.getenv("PIPELINE_CONSUMER_ONLY", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
        "on",
    )
    symbols_path = Path(__file__).with_name("symbols.txt")
    symbols = []
    if symbols_path.exists():
        for line in symbols_path.read_text().splitlines():
            item = line.strip()
            if not item or item.startswith("#"):
                continue
            symbols.append(item)
    if not symbols:
        symbols = ["HOOD"]

    cfg = load_strategy_params_from_ssot(strategy_id, strategy_version)
    for symbol in symbols:
        run_id = f"dev_{ts}_{symbol}"
        out_dir = get_backtest_run_dir(run_id)
        bars_path = out_dir / "bars_snapshot.parquet"
        params = {
            **cfg.get("core", {}),
            **cfg.get("tunable", {}),
            "symbol": symbol,
            "timeframe": "M5",
            "requested_end": requested_end,
            "lookback_days": 0,
            "valid_from_policy": "signal_ts",
            "order_validity_policy": "session_end",
            "consumer_only": consumer_only,
        }
        params.setdefault("strategy_version", strategy_version)
        params.setdefault("backtesting", {})
        params["backtesting"].update(
            {
                "compound_sizing": True,
                "compound_equity_basis": "cash_only",
            }
        )

        run_pipeline(
            run_id=run_id,
            out_dir=out_dir,
            bars_path=bars_path,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            strategy_params=params,
            strategy_meta=cfg,
            compound_enabled=True,
            compound_equity_basis="cash_only",
            initial_cash=10000.0,
            fees_bps=2.0,
            slippage_bps=1.0,
        )
