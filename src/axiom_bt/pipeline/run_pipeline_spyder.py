#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 12 22:19:59 2026

@author: mirko
"""

# run_pipeline_spyder.py
import sys
from pathlib import Path
from datetime import datetime

# Ensure local source takes precedence (avoid stale installed package)
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axiom_bt.pipeline.cli import main

if __name__ == "__main__":
    ts = datetime.now().strftime("%y%m%d_%H%M%S")
    run_id = f"dev_{ts}"
    out_dir = ROOT / "artifacts" / "backtest" / run_id

    argv = [
        "--run-id", run_id,
        "--out-dir", out_dir,
        "--bars-path", "/pfad/zu/bars.csv",
        "--strategy-id", "insidebar_intraday",
        "--strategy-version", "1.0.0",
        "--symbol", "HOOD",
        "--timeframe", "M5",
        "--valid-to", "2026-01-10",       # Ende der Datenperiode (ISO)
        "--lookback-days", "40",          # Lookback ohne Warmup (alternativ --valid-from)
        "--initial-cash", "10000",
        "--compound-enabled",       # weglassen, wenn aus
        "--fees-bps", "0",
        "--slippage-bps", "0",
    ]
    main(argv)
