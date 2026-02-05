"""Deterministic FillModel SSOT.

Produces fills from intent + bars; fill timestamp/price/reason are defined here only.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Tuple

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

    bars = bars.copy()
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True)
    bars = bars.sort_values("timestamp").reset_index(drop=True)
    bar_idx = bars.set_index("timestamp")
    rows = []
    for _, intent in events_intent.iterrows():
        ts = pd.to_datetime(intent["signal_ts"], utc=True)
        if ts not in bar_idx.index:
            # reject deterministically
            raise FillModelError(f"entry bar not found for signal_ts={ts}")
        bar = bar_idx.loc[ts]
        price = float(bar["close"])
        side = intent.get("side")
        if side is None or pd.isna(side):
            raise FillModelError("intent missing side for exit simulation")
        side = str(side).upper()
        trigger_level = intent.get("entry_price")
        if (
            intent.get("strategy_id") == "insidebar_intraday"
            and pd.notna(trigger_level)
        ):
            price, reason_code = _entry_fill_stop_cross(
                side,
                float(trigger_level),
                bar,
            )
            logger.info(
                "actions: entry_fill_stop_cross side=%s trig=%s open=%s high=%s low=%s fill=%s reason=%s template_id=%s signal_ts=%s",
                side,
                float(trigger_level),
                float(bar.get("open", float("nan"))),
                float(bar.get("high", float("nan"))),
                float(bar.get("low", float("nan"))),
                float(price),
                reason_code,
                intent.get("template_id"),
                ts,
            )
        stop_price = intent.get("stop_price")
        tp_price = intent.get("take_profit_price")
        if pd.isna(stop_price) or pd.isna(tp_price):
            raise FillModelError("intent missing stop_price or take_profit_price")
        rows.append(
            {
                "template_id": intent["template_id"],
                "symbol": intent.get("symbol", "UNKNOWN"),
                "fill_ts": ts,
                "fill_price": price,
                "reason": "signal_fill",
            }
        )
        # Determine valid_to for exit simulation (contract: order_valid_to_ts)
        if pd.notna(intent.get("order_valid_to_ts")):
            valid_to = pd.to_datetime(intent["order_valid_to_ts"], utc=True)
        else:
            if order_validity_policy != "session_end":
                raise FillModelError(
                    "order_valid_to_ts missing and order_validity_policy is not session_end"
                )
            if not session_timezone or not session_filter:
                raise FillModelError(
                    "exit_ts missing and session_end requires session_timezone + session_filter"
                )
            valid_to = session_end_for_day(ts, session_filter, session_timezone)
        # Scan bars after entry up to valid_to inclusive
        scan = bars[(bars["timestamp"] > ts) & (bars["timestamp"] <= valid_to)]
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
