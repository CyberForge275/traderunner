"""Intent generation skeleton for perlentaucher_daily_scan."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd
from pandas.tseries.offsets import BDay

from axiom_bt.artifacts.intent_contract import sanitize_intent


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
    "order_valid_from_ts",
    "order_valid_to_ts",
    "order_valid_to_reason",
]


def _hash_dataframe(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest()


def generate_intent(
    signals_frame: pd.DataFrame,
    strategy_id: str,
    strategy_version: str,
    params: dict,
) -> IntentArtifacts:
    _ = params
    if signals_frame.empty:
        events_intent = pd.DataFrame(columns=INTENT_COLUMNS)
        return IntentArtifacts(
            signals_frame=signals_frame,
            events_intent=events_intent,
            intent_hash=_hash_dataframe(events_intent),
        )

    if "signal_side" not in signals_frame.columns:
        events_intent = pd.DataFrame(columns=INTENT_COLUMNS)
        return IntentArtifacts(
            signals_frame=signals_frame,
            events_intent=events_intent,
            intent_hash=_hash_dataframe(events_intent),
        )

    active = signals_frame[signals_frame["signal_side"].notna()].copy()
    if active.empty:
        events_intent = pd.DataFrame(columns=INTENT_COLUMNS)
        return IntentArtifacts(
            signals_frame=signals_frame,
            events_intent=events_intent,
            intent_hash=_hash_dataframe(events_intent),
        )

    required = [
        "signal_ts",
        "symbol",
        "signal_side",
        "entry_price",
        "stop_price",
        "take_profit_price",
        "template_id",
        "oco_group_id",
    ]
    missing = [col for col in required if col not in active.columns]
    if missing:
        raise ValueError(
            "perlentaucher_daily_scan generate_intent missing signal columns: "
            + ", ".join(sorted(missing))
        )

    intents: list[dict] = []
    for _, row in active.iterrows():
        signal_ts = pd.to_datetime(row["signal_ts"], utc=True)
        valid_from = signal_ts + BDay(1)
        raw_intent = {
            "template_id": str(row["template_id"]),
            "signal_ts": signal_ts,
            "symbol": str(row["symbol"]).upper(),
            "side": str(row["signal_side"]).upper(),
            "entry_price": float(row["entry_price"]),
            "stop_price": float(row["stop_price"]),
            "take_profit_price": float(row["take_profit_price"]),
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "oco_group_id": str(row["oco_group_id"]),
            "order_valid_from_ts": valid_from,
            "order_valid_to_ts": valid_from,
            "order_valid_to_reason": "next_day_only",
        }
        intents.append(
            sanitize_intent(
                raw_intent,
                intent_generated_ts=signal_ts,
                strict=False,
                run_id=params.get("run_id"),
                template_id=raw_intent["template_id"],
            )
        )

    events_intent = pd.DataFrame(intents)
    if not events_intent.empty:
        events_intent = events_intent.sort_values(
            ["signal_ts", "template_id", "side"],
            kind="mergesort",
        ).reset_index(drop=True)
    else:
        events_intent = pd.DataFrame(columns=INTENT_COLUMNS)
    return IntentArtifacts(
        signals_frame=signals_frame,
        events_intent=events_intent,
        intent_hash=_hash_dataframe(events_intent),
    )
