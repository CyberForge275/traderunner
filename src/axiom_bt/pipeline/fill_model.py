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
        # Determine valid_to for exit simulation
        if pd.notna(intent.get("exit_ts")):
            valid_to = pd.to_datetime(intent["exit_ts"], utc=True)
        else:
            if order_validity_policy != "session_end":
                raise FillModelError(
                    "exit_ts missing and order_validity_policy is not session_end"
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
