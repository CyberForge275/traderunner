"""Signal and intent generation (frozen stream SSOT).

This module produces a deterministic intent stream from bars and strategy params.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Tuple

import pandas as pd

from trade.session_windows import session_end_for_day

logger = logging.getLogger(__name__)

ORDER_CONTEXT_COLUMNS_DEFAULT = [
    "atr",
    "inside_bar",
    "mother_high",
    "mother_low",
    "entry_price",
    "stop_price",
    "take_profit_price",
    "signal_ts",
    "mother_ts",
    "inside_ts",
    "breakout_ts",
]


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
        context_cols = params.get("order_context_columns", ORDER_CONTEXT_COLUMNS_DEFAULT)
        order_validity_policy = params.get("order_validity_policy")
        session_timezone = params.get("session_timezone")
        session_filter = params.get("session_filter")
        valid_from_policy = params.get("valid_from_policy")
        timeframe_minutes = params.get("timeframe_minutes")
        intents = []
        for _, sig in active_signals.iterrows():
            signal_ts = pd.to_datetime(sig["timestamp"], utc=True)
            intent = {
                "template_id": str(sig["template_id"]),
                "signal_ts": signal_ts,
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
            if valid_from_policy:
                intent["dbg_effective_valid_from_policy"] = valid_from_policy

            if order_validity_policy == "session_end":
                if not session_timezone or not session_filter:
                    raise IntentGenerationError(
                        "order_validity_policy=session_end requires session_timezone and session_filter"
                    )
                exit_ts = session_end_for_day(signal_ts, session_filter, session_timezone)
                intent["exit_ts"] = exit_ts
                intent["exit_reason"] = "session_end"
                intent["dbg_valid_to_ts_utc"] = exit_ts
                intent["dbg_valid_to_ts_ny"] = exit_ts.tz_convert("America/New_York")
                intent["dbg_valid_to_ts"] = exit_ts.tz_convert(session_timezone)

            if valid_from_policy in {"signal_ts", "next_bar"}:
                if valid_from_policy == "signal_ts":
                    valid_from = signal_ts
                else:
                    if timeframe_minutes is None:
                        raise IntentGenerationError(
                            "valid_from_policy=next_bar requires timeframe_minutes in params"
                        )
                    valid_from = signal_ts + pd.Timedelta(minutes=int(timeframe_minutes))
                intent["dbg_valid_from_ts_utc"] = valid_from
                if session_timezone:
                    intent["dbg_valid_from_ts"] = valid_from.tz_convert(session_timezone)
                intent["dbg_valid_from_ts_ny"] = valid_from.tz_convert("America/New_York")

            for col in context_cols:
                if col in sig.index:
                    intent[f"sig_{col}"] = sig[col]
            intents.append(intent)
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
