"""Intent generation skeleton for ndx_momentum_rotation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class IntentArtifacts:
    signals_frame: pd.DataFrame
    events_intent: pd.DataFrame
    intent_hash: str


INTENT_COLUMNS = [
    "template_id",
    "signal_ts",
    "symbol",
    "side",
    "entry_price",
    "stop_price",
    "take_profit_price",
    "strategy_id",
    "strategy_version",
    "oco_group_id",
    "order_valid_to_ts",
    "order_valid_to_reason",
]


def _hash_dataframe(df: pd.DataFrame) -> str:
    data = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def generate_intent(
    signals_frame: pd.DataFrame,
    strategy_id: str,
    strategy_version: str,
    params: dict,
) -> IntentArtifacts:
    """Return an empty but schema-compatible intent frame for skeleton phase."""

    _ = (signals_frame, strategy_id, strategy_version, params)
    events_intent = pd.DataFrame(columns=INTENT_COLUMNS)
    return IntentArtifacts(
        signals_frame=signals_frame,
        events_intent=events_intent,
        intent_hash=_hash_dataframe(events_intent),
    )
