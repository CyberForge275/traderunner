"""Strategy-owned intent generation (legacy logic, frozen stream SSOT)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import pandas as pd

from trade.session_windows import session_window_end_for_ts
from axiom_bt.artifacts.intent_contract import sanitize_intent

logger = logging.getLogger(__name__)

ORDER_CONTEXT_COLUMNS_DEFAULT = [
    "atr",
    "inside_bar",
    "mother_high",
    "mother_low",
    "mother_body_fraction",
    "inside_body_fraction",
    "entry_price",
    "stop_price",
    "take_profit_price",
    "signal_ts",
    "mother_ts",
    "inside_ts",
    "breakout_ts",
]

DBG_CONTEXT_MAP = {
    "breakout_level": "dbg_breakout_level",
    "mother_high": "dbg_mother_high",
    "mother_low": "dbg_mother_low",
    "mother_range": "dbg_mother_range",
    "mother_ts": "dbg_mother_ts",
    "inside_ts": "dbg_inside_ts",
    "trigger_ts": "dbg_trigger_ts",
    "order_expired": "dbg_order_expired",
    "order_expire_reason": "dbg_order_expire_reason",
}


class IntentGenerationError(ValueError):
    """Raised when signals or intent cannot be produced."""


@dataclass(frozen=True)
class IntentArtifacts:
    signals_frame: pd.DataFrame
    events_intent: pd.DataFrame
    intent_hash: str


def _hash_dataframe(df: pd.DataFrame) -> str:
    data = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _canonicalize_events_intent(events_intent: pd.DataFrame) -> pd.DataFrame:
    sort_cols = [c for c in ("signal_ts", "template_id", "side") if c in events_intent.columns]
    if sort_cols:
        return events_intent.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
    return events_intent


def generate_intent(
    signals_frame: pd.DataFrame,
    strategy_id: str,
    strategy_version: str,
    params: dict,
) -> IntentArtifacts:
    """Generate deterministic intent from a strategy-enriched SignalFrame."""
    if signals_frame.empty:
        raise IntentGenerationError("signals_frame empty; cannot generate intent")

    active_signals = signals_frame[signals_frame["signal_side"].notna()].copy()

    if active_signals.empty:
        logger.warning("actions: generate_intent_no_signals strategy=%s version=%s", strategy_id, strategy_version)
        events_intent = pd.DataFrame(
            columns=[
                "template_id",
                "signal_ts",
                "symbol",
                "side",
                "entry_price",
                "stop_price",
                "take_profit_price",
                "strategy_id",
                "strategy_version",
            ]
        )
    else:
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
                "oco_group_id": sig.get("oco_group_id"),
                "entry_price": float(sig["entry_price"]) if pd.notna(sig["entry_price"]) else None,
                "stop_price": float(sig["stop_price"]) if pd.notna(sig["stop_price"]) else None,
                "take_profit_price": float(sig["take_profit_price"]) if pd.notna(sig["take_profit_price"]) else None,
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
            }
            if pd.notna(intent.get("side")) and pd.isna(intent.get("oco_group_id")):
                raise IntentGenerationError("missing oco_group_id for signal row")
            intent["breakout_confirmation"] = params.get("breakout_confirmation")
            intent["dbg_signal_ts_ny"] = signal_ts.tz_convert("America/New_York")
            intent["dbg_signal_ts_berlin"] = signal_ts.tz_convert("Europe/Berlin")
            effective_valid_from_policy = valid_from_policy
            if effective_valid_from_policy:
                intent["dbg_effective_valid_from_policy"] = effective_valid_from_policy

            if order_validity_policy == "session_end":
                if not session_timezone or not session_filter:
                    raise IntentGenerationError(
                        "order_validity_policy=session_end requires session_timezone and session_filter"
                    )
                exit_ts = session_window_end_for_ts(signal_ts, session_filter, session_timezone)
                intent["order_valid_to_ts"] = exit_ts
                intent["order_valid_to_reason"] = "session_end"
                intent["dbg_valid_to_ts_utc"] = exit_ts
                intent["dbg_valid_to_ts_ny"] = exit_ts.tz_convert("America/New_York")
                intent["dbg_valid_to_ts"] = exit_ts.tz_convert(session_timezone)

            if effective_valid_from_policy in {"signal_ts", "next_bar"}:
                if effective_valid_from_policy == "signal_ts":
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
            for src_col, dbg_col in DBG_CONTEXT_MAP.items():
                if src_col in sig.index:
                    intent[dbg_col] = sig[src_col]
            if "mother_high" in sig.index:
                intent["dbg_mother_high"] = sig["mother_high"]
            if "mother_low" in sig.index:
                intent["dbg_mother_low"] = sig["mother_low"]
            if pd.notna(intent.get("dbg_mother_high")) and pd.notna(intent.get("dbg_mother_low")):
                intent["dbg_mother_range"] = float(intent["dbg_mother_high"]) - float(intent["dbg_mother_low"])
            if "inside_ts" in sig.index:
                intent["dbg_inside_ts"] = pd.to_datetime(sig["inside_ts"], utc=True) if pd.notna(sig["inside_ts"]) else None
            if "mother_ts" in sig.index:
                intent["dbg_mother_ts"] = pd.to_datetime(sig["mother_ts"], utc=True) if pd.notna(sig["mother_ts"]) else None
            if "breakout_level" in sig.index and pd.notna(sig["breakout_level"]):
                intent["dbg_breakout_level"] = float(sig["breakout_level"])
            elif pd.notna(sig.get("entry_price")):
                intent["dbg_breakout_level"] = float(sig["entry_price"])
            if "order_expired" in sig.index and pd.notna(sig["order_expired"]):
                intent["dbg_order_expired"] = bool(sig["order_expired"])
            else:
                intent["dbg_order_expired"] = False
            if "order_expire_reason" in sig.index and pd.notna(sig["order_expire_reason"]):
                intent["dbg_order_expire_reason"] = sig["order_expire_reason"]
            intents.append(
                sanitize_intent(
                    intent,
                    intent_generated_ts=signal_ts,
                    strict=bool(params.get("strict_intent_contract", False)),
                    run_id=params.get("run_id"),
                    template_id=intent.get("template_id"),
                )
            )
        events_intent = pd.DataFrame(intents)

    events_intent = _canonicalize_events_intent(events_intent)
    intent_hash = _hash_dataframe(events_intent)
    logger.info(
        "actions: intent_frozen strategy=%s version=%s intent_hash=%s events=%d",
        strategy_id,
        strategy_version,
        intent_hash,
        len(events_intent),
    )
    return IntentArtifacts(signals_frame=signals_frame, events_intent=events_intent, intent_hash=intent_hash)
