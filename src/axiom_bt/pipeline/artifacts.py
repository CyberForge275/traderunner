"""Artifact writing for the modular pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)


class ArtifactError(ValueError):
    """Raised when artifacts cannot be written."""


def write_frame(df: pd.DataFrame, path: Path) -> None:
    """Persist a DataFrame to CSV/Parquet (index dropped)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)


def write_artifacts(
    out_dir: Path,
    *,
    signals_frame: pd.DataFrame,
    events_intent: pd.DataFrame,
    fills: pd.DataFrame,
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
    ledger: pd.DataFrame,
    manifest_fields: Dict,
    result_fields: Dict,
    metrics: Dict,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # signals_frame is used for computation but not persisted to disk (Proof of runtime validation only)
    write_frame(events_intent, out_dir / "events_intent.csv")
    write_frame(fills, out_dir / "fills.csv")
    write_frame(trades, out_dir / "trades.csv")
    write_frame(equity_curve, out_dir / "equity_curve.csv")
    write_frame(ledger, out_dir / "portfolio_ledger.csv")

    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    manifest_path = out_dir / "run_manifest.json"
    result_path = out_dir / "run_result.json"
    meta_path = out_dir / "run_meta.json"

    manifest_path.write_text(json.dumps(manifest_fields, indent=2))
    result_path.write_text(json.dumps(result_fields, indent=2))
    meta_path.write_text(json.dumps({"run_id": manifest_fields.get("run_id"), "params": manifest_fields.get("params")}, indent=2))

    logger.info("actions: artifacts_written dir=%s", out_dir)
