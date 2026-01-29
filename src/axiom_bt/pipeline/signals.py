"""Signal and intent generation (frozen stream SSOT).

This module produces a deterministic intent stream from bars and strategy params.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class IntentGenerationError(ValueError):
    """Raised when signals or intent cannot be produced."""


@dataclass(frozen=True)
class IntentArtifacts:
    signals_frame: pd.DataFrame
    events_intent: pd.DataFrame
    intent_hash: str


def _hash_dataframe(df: pd.DataFrame) -> str:
    # Hash CSV bytes for deterministic intent hash
    data = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def generate_intent(signals_frame: pd.DataFrame, strategy_id: str, strategy_version: str, params: dict) -> IntentArtifacts:
    """Generate deterministic intent from a strategy-enriched SignalFrame.

    Args:
        signals_frame: Validated SignalFrame with strategy-specific indicator and signal columns.
        strategy_id: strategy identifier.
        strategy_version: version string.
        params: strategy parameters (dict).

    Returns:
        IntentArtifacts with signals_frame, events_intent, intent_hash.
    """
    if signals_frame.empty:
        raise IntentGenerationError("signals_frame empty; cannot generate intent")

    # Filter for active signals based on the contract: signal_side is not null
    active_signals = signals_frame[signals_frame["signal_side"].notna()].copy()

    if active_signals.empty:
        logger.warning("actions: generate_intent_no_signals strategy=%s version=%s", strategy_id, strategy_version)
        # We still return empty events_intent to allow pipeline to continue/artifacts to be written
        events_intent = pd.DataFrame(columns=["template_id", "signal_ts", "symbol", "side", "entry_price", "stop_price", "take_profit_price", "strategy_id", "strategy_version"])
    else:
        # Build deterministic intent stream using strategy-owned columns
        intents = []
        for _, sig in active_signals.iterrows():
            intents.append(
                {
                    "template_id": str(sig["template_id"]),
                    "signal_ts": pd.to_datetime(sig["timestamp"], utc=True),
                    "symbol": sig["symbol"],
                    "side": sig["signal_side"],
                    "entry_price": float(sig["entry_price"]) if pd.notna(sig["entry_price"]) else None,
                    "stop_price": float(sig["stop_price"]) if pd.notna(sig["stop_price"]) else None,
                    "take_profit_price": float(sig["take_profit_price"]) if pd.notna(sig["take_profit_price"]) else None,
                    "exit_ts": pd.to_datetime(sig["exit_ts"], utc=True) if pd.notna(sig["exit_ts"]) else None,
                    "exit_reason": sig["exit_reason"] if pd.notna(sig["exit_reason"]) else None,
                    "strategy_id": strategy_id,
                    "strategy_version": strategy_version,
                }
            )
        events_intent = pd.DataFrame(intents)

    intent_hash = _hash_dataframe(events_intent)
    logger.info(
        "actions: intent_frozen strategy=%s version=%s intent_hash=%s events=%d",
        strategy_id,
        strategy_version,
        intent_hash,
        len(events_intent),
    )
    return IntentArtifacts(signals_frame=signals_frame, events_intent=events_intent, intent_hash=intent_hash)
