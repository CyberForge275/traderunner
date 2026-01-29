"""Deterministic FillModel SSOT.

Produces fills from intent + bars; fill timestamp/price/reason are defined here only.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class FillModelError(ValueError):
    """Raised when fills cannot be generated."""


@dataclass(frozen=True)
class FillArtifacts:
    fills: pd.DataFrame
    fills_hash: str


def _hash_dataframe(df: pd.DataFrame) -> str:
    data = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def generate_fills(events_intent: pd.DataFrame, bars: pd.DataFrame) -> FillArtifacts:
    """Generate deterministic fills by matching intent signal_ts to bar closes.

    Logic: For each intent, pick the bar whose timestamp == signal_ts; fill at close.
    If no bar matches exactly, fill is rejected.

    Returns:
        FillArtifacts with fills DataFrame and fills_hash.
    """
    if events_intent.empty:
        fills = pd.DataFrame(
            columns=["template_id", "symbol", "fill_ts", "fill_price", "reason"]
        )
        fills_hash = _hash_dataframe(fills)
        logger.warning("actions: fills_empty_intent fills_hash=%s", fills_hash)
        return FillArtifacts(fills=fills, fills_hash=fills_hash)
    if bars.empty:
        raise FillModelError("bars empty; cannot generate fills")

    bar_idx = bars.set_index("timestamp")
    rows = []
    for _, intent in events_intent.iterrows():
        ts = pd.to_datetime(intent["signal_ts"], utc=True)
        if ts not in bar_idx.index:
            # reject deterministically
            continue
        bar = bar_idx.loc[ts]
        price = float(bar["close"])
        rows.append(
            {
                "template_id": intent["template_id"],
                "symbol": intent.get("symbol", "UNKNOWN"),
                "fill_ts": ts,
                "fill_price": price,
                "reason": "signal_fill",
            }
        )

    fills = pd.DataFrame(rows)
    if fills.empty:
        fills = pd.DataFrame(
            columns=["template_id", "symbol", "fill_ts", "fill_price", "reason"]
        )
        fills_hash = _hash_dataframe(fills)
        logger.warning("actions: fills_empty_no_match fills_hash=%s", fills_hash)
        return FillArtifacts(fills=fills, fills_hash=fills_hash)

    fills_hash = _hash_dataframe(fills)
    logger.info("actions: fills_generated fills_hash=%s fills=%d", fills_hash, len(fills))
    return FillArtifacts(fills=fills, fills_hash=fills_hash)
