"""Data preparation for the pipeline: load bars snapshot and hash it.

Deterministic, read-only: never mutates source data.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class BarsLoadError(ValueError):
    """Raised when bars snapshot cannot be loaded or validated."""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_bars_snapshot(path: Path) -> Tuple[pd.DataFrame, str]:
    """Load OHLCV bars snapshot (csv or parquet) and return frame + hash.

    Args:
        path: File path to bars snapshot (csv or parquet).

    Returns:
        (bars_df, bars_hash)

    Raises:
        BarsLoadError: if file missing or unsupported format.
    """
    if not path.exists():
        raise BarsLoadError(f"bars snapshot not found: {path}")

    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            bars = pd.read_csv(path)
        elif suffix in (".parquet", ".pq"):
            bars = pd.read_parquet(path)
        else:
            raise BarsLoadError(f"unsupported bars format: {path.suffix}")
    except Exception as exc:  # pragma: no cover - propagated
        raise BarsLoadError(f"failed to load bars: {path}: {exc}") from exc

    # If index carries timestamps, surface as column (legacy intraday parquet)
    if "timestamp" not in bars.columns and isinstance(bars.index, pd.DatetimeIndex):
        bars = bars.copy()
        bars["timestamp"] = bars.index
        bars = bars.reset_index(drop=True)

    # normalize column casing
    bars = bars.rename(columns={c: c.lower() for c in bars.columns})

    required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required_cols - set(bars.columns)
    if missing:
        raise BarsLoadError(f"bars missing required columns: {missing}")

    bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    bars = bars.sort_values("timestamp").reset_index(drop=True)

    bars_hash = _sha256_file(path)
    logger.info("actions: bars_snapshot_loaded path=%s hash=%s rows=%d", path, bars_hash, len(bars))
    return bars, bars_hash
