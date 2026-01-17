"""Metrics wrapper for pipeline (UI contract)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

import pandas as pd

from axiom_bt.metrics import compose_metrics

logger = logging.getLogger(__name__)


def compute_and_write_metrics(trades: pd.DataFrame, equity: pd.DataFrame, initial_cash: float, out_path: Path) -> Dict[str, float]:
    """Compute simple PnL/return stats and write metrics.json."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    metrics = compose_metrics(trades, equity, initial_cash)
    out_path.write_text(json.dumps(metrics, indent=2))
    logger.info("actions: metrics_written path=%s", out_path)
    return metrics
