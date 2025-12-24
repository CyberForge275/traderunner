"""
Artifacts Index Writer - SSOT for artifact discovery.

Generates artifacts_index.json listing all persisted artifacts
with metadata (rows, bytes, schema) for deterministic discovery.
"""

from pathlib import Path
from datetime import datetime, timezone
import json
import pandas as pd
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def write_artifacts_index(run_dir: Path) -> None:
    """
    Generate artifacts_index.json for deterministic discovery.

    Scans run directory for known artifact patterns and creates
    a registry with metadata (rows, bytes, schema).

    Args:
        run_dir: Run artifacts directory
    """
    artifacts: List[Dict[str, Any]] = []

    # Known artifact patterns (kind, filename)
    artifact_patterns = [
        ("equity_curve", "equity_curve.csv"),
        ("orders", "orders.csv"),
        ("filled_orders", "filled_orders.csv"),
        ("trades", "trades.csv"),
        ("metrics", "metrics.json"),
    ]

    for kind, filename in artifact_patterns:
        filepath = run_dir / filename

        if not filepath.exists():
            continue

        # Base metadata
        entry: Dict[str, Any] = {
            "kind": kind,
            "relpath": filename,
            "format": filepath.suffix.lstrip('.'),
            "bytes": filepath.stat().st_size
        }

        # Add rows + schema for CSV files
        if filename.endswith(".csv"):
            try:
                df = pd.read_csv(filepath)
                entry["rows"] = len(df)
                entry["schema"] = list(df.columns)
            except Exception as e:
                logger.warning(f"Could not read {filename} for metadata: {e}")
                entry["rows"] = None
                entry["schema"] = None

        artifacts.append(entry)

    # Write index
    index = {
        "artifacts": artifacts,
        "indexed_at": datetime.now(timezone.utc).isoformat()
    }

    index_path = run_dir / "artifacts_index.json"
    index_path.write_text(json.dumps(index, indent=2))

    logger.info(f"[{run_dir.name}] Wrote artifacts_index.json ({len(artifacts)} entries)")
