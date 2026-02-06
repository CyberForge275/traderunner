"""Deterministic FillModel SSOT.

Produces fills from intent + bars; fill timestamp/price/reason are defined here only.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd

from trade.session_windows import session_end_for_day

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


def _entry_fill_stop_cross(
    side: str,
    trigger_level: float,
    bar: pd.Series,
) -> Tuple[float, str]:
    """Determine entry fill price for stop/crossing logic.

    Returns (fill_price, reason_code). reason_code is for logging only.
    """
    try:
        open_px = float(bar["open"])
        high_px = float(bar["high"])
        low_px = float(bar["low"])
    except Exception:
        return float(bar["close"]), "missing_ohlc"

    if side == "SELL":
        if open_px <= trigger_level:
            return open_px, "gap_open"
        if high_px >= trigger_level >= low_px:
            return trigger_level, "cross_in_bar"
        return float(bar["close"]), "no_cross"
    # BUY
    if open_px >= trigger_level:
        return open_px, "gap_open"
    if high_px >= trigger_level >= low_px:
        return trigger_level, "cross_in_bar"
    return float(bar["close"]), "no_cross"


def generate_fills(
    events_intent: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    order_validity_policy: str | None = None,
    session_timezone: str | None = None,
    session_filter: list[str] | None = None,
) -> FillArtifacts:
    """Generate deterministic fills by trigger-scanning bars from signal_ts.

    OCO semantics (if oco_group_id present):
    - At most one entry fill per group.
    - On first fill, cancel the other leg(s) with reason=order_cancelled_oco.
    - If both legs trigger in the same bar => no fills, emit order_ambiguous_no_fill.
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

    bars = bars.copy()
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True)
    bars = bars.sort_values("timestamp").reset_index(drop=True)
    bar_idx = bars.set_index("timestamp")
    rows: List[Dict] = []

    def _valid_to_for(intent_row: pd.Series, signal_ts: pd.Timestamp) -> pd.Timestamp:
        if pd.notna(intent_row.get("order_valid_to_ts")):
            return pd.to_datetime(intent_row["order_valid_to_ts"], utc=True)
        if order_validity_policy != "session_end":
            raise FillModelError(
                "order_valid_to_ts missing and order_validity_policy is not session_end"
            )
        if not session_timezone or not session_filter:
            raise FillModelError(
                "exit_ts missing and session_end requires session_timezone + session_filter"
            )
        return session_end_for_day(signal_ts, session_filter, session_timezone)

    def _find_trigger_bar(intent_row: pd.Series, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.Series | None:
        side = str(intent_row.get("side", "")).upper()
        entry_px = intent_row.get("entry_price")
        if pd.isna(entry_px):
            return None
        window = bars[(bars["timestamp"] >= start_ts) & (bars["timestamp"] <= end_ts)]
        if window.empty:
            return None
        if side == "BUY":
            match = window[window["high"] >= float(entry_px)]
        else:  # SELL
            match = window[window["low"] <= float(entry_px)]
        if match.empty:
            return None
        return match.iloc[0]

    # Group by OCO group if present, else one-per-template
    intents = events_intent.copy()
    if "oco_group_id" not in intents.columns:
        intents["oco_group_id"] = pd.NA
    intents["oco_group_id"] = intents["oco_group_id"].fillna(intents["template_id"])
    intents = intents.sort_values(["signal_ts", "template_id"]).reset_index(drop=True)

    netting_open_until: dict[str, pd.Timestamp] = {}
    netting_open_by_template: dict[str, str] = {}
    for oco_group_id, group in intents.groupby("oco_group_id", sort=False):
        group_triggers = []
        for _, intent in group.iterrows():
            signal_ts = pd.to_datetime(intent["signal_ts"], utc=True)
            valid_to = _valid_to_for(intent, signal_ts)
            trigger_bar = _find_trigger_bar(intent, signal_ts, valid_to)
            if trigger_bar is not None:
                group_triggers.append((intent, trigger_bar, signal_ts))

        if not group_triggers:
            continue

        # If multiple legs trigger in same bar, mark ambiguous and skip fills
        if len(group_triggers) > 1:
            first_ts = group_triggers[0][1]["timestamp"]
            if all(trig[1]["timestamp"] == first_ts for trig in group_triggers):
                for intent, trig_bar, _ in group_triggers:
                    rows.append(
                        {
                            "template_id": intent["template_id"],
                            "symbol": intent.get("symbol", "UNKNOWN"),
                            "fill_ts": trig_bar["timestamp"],
                            "fill_price": float("nan"),
                            "reason": "order_ambiguous_no_fill",
                            "side": intent.get("side"),
                            "oco_group_id": oco_group_id,
                            "cancel_reason": "oco_ambiguous",
                        }
                    )
                continue

        # Pick earliest trigger bar (deterministic)
        group_triggers.sort(key=lambda t: (t[1]["timestamp"], str(t[0].get("template_id"))))
        intent, trigger_bar, signal_ts = group_triggers[0]
        side = intent.get("side")
        if side is None or pd.isna(side):
            raise FillModelError("intent missing side for exit simulation")
        side = str(side).upper()
        symbol = intent.get("symbol", "UNKNOWN")
        netting_mode = intent.get("netting_mode", "one_position_per_symbol")
        if netting_mode == "one_position_per_symbol":
            blocked_until = netting_open_until.get(symbol)
            if blocked_until is not None and trigger_bar["timestamp"] <= blocked_until:
                rows.append(
                    {
                        "template_id": intent["template_id"],
                        "symbol": symbol,
                        "fill_ts": trigger_bar["timestamp"],
                        "fill_price": float("nan"),
                        "reason": "order_rejected_netting_open_position",
                        "side": side,
                        "oco_group_id": oco_group_id,
                        "blocked_until": blocked_until.isoformat(),
                        "blocked_by_template_id": netting_open_by_template.get(symbol),
                    }
                )
                continue
        trigger_level = intent.get("entry_price")
        if pd.isna(trigger_level):
            continue

        price, reason_code = _entry_fill_stop_cross(
            side,
            float(trigger_level),
            trigger_bar,
        )
        logger.info(
            "actions: entry_fill_stop_cross side=%s trig=%s open=%s high=%s low=%s fill=%s reason=%s template_id=%s signal_ts=%s",
            side,
            float(trigger_level),
            float(trigger_bar.get("open", float("nan"))),
            float(trigger_bar.get("high", float("nan"))),
            float(trigger_bar.get("low", float("nan"))),
            float(price),
            reason_code,
            intent.get("template_id"),
            signal_ts,
        )

        rows.append(
            {
                "template_id": intent["template_id"],
                "symbol": symbol,
                "fill_ts": trigger_bar["timestamp"],
                "fill_price": price,
                "reason": "signal_fill",
                "side": side,
                "oco_group_id": oco_group_id,
            }
        )

        # Cancel remaining legs in group
        for _, other_intent in group.iterrows():
            if other_intent["template_id"] == intent["template_id"]:
                continue
            rows.append(
                {
                    "template_id": other_intent["template_id"],
                    "symbol": other_intent.get("symbol", "UNKNOWN"),
                    "fill_ts": trigger_bar["timestamp"],
                    "fill_price": float("nan"),
                    "reason": "order_cancelled_oco",
                    "side": other_intent.get("side"),
                    "oco_group_id": oco_group_id,
                    "cancel_reason": "oco_cancelled",
                }
            )

        # Exit simulation only for the filled intent
        stop_price = intent.get("stop_price")
        tp_price = intent.get("take_profit_price")
        if pd.isna(stop_price) or pd.isna(tp_price):
            raise FillModelError("intent missing stop_price or take_profit_price")
        valid_to = _valid_to_for(intent, signal_ts)
        scan = bars[(bars["timestamp"] > trigger_bar["timestamp"]) & (bars["timestamp"] <= valid_to)]
        exit_row = None
        for _, bar_row in scan.iterrows():
            bar_ts = bar_row["timestamp"]
            if side == "BUY":
                stop_hit = float(bar_row["low"]) <= float(stop_price)
                tp_hit = float(bar_row["high"]) >= float(tp_price)
            else:  # SELL
                stop_hit = float(bar_row["high"]) >= float(stop_price)
                tp_hit = float(bar_row["low"]) <= float(tp_price)
            if stop_hit and tp_hit:
                exit_row = {
                    "template_id": intent["template_id"],
                    "symbol": intent.get("symbol", "UNKNOWN"),
                    "fill_ts": bar_ts,
                    "fill_price": float(stop_price),
                    "reason": "stop_loss",
                }
                break
            if stop_hit:
                exit_row = {
                    "template_id": intent["template_id"],
                    "symbol": intent.get("symbol", "UNKNOWN"),
                    "fill_ts": bar_ts,
                    "fill_price": float(stop_price),
                    "reason": "stop_loss",
                }
                break
            if tp_hit:
                exit_row = {
                    "template_id": intent["template_id"],
                    "symbol": intent.get("symbol", "UNKNOWN"),
                    "fill_ts": bar_ts,
                    "fill_price": float(tp_price),
                    "reason": "take_profit",
                }
                break
        if exit_row is None:
            if valid_to not in bar_idx.index:
                raise FillModelError(f"exit bar not found for valid_to={valid_to}")
            exit_bar = bar_idx.loc[valid_to]
            exit_row = {
                "template_id": intent["template_id"],
                "symbol": intent.get("symbol", "UNKNOWN"),
                "fill_ts": valid_to,
                "fill_price": float(exit_bar["close"]),
                "reason": "session_end",
            }
        rows.append(exit_row)
        # Update netting window after exit determination
        if netting_mode == "one_position_per_symbol":
            netting_open_until[symbol] = pd.to_datetime(exit_row["fill_ts"], utc=True)
            netting_open_by_template[symbol] = intent["template_id"]

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
