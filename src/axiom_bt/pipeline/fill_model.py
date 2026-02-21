"""Deterministic FillModel SSOT.

Produces fills from intent + bars; fill timestamp/price/reason are defined here only.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import pandas as pd

from trade.session_windows import session_end_for_day

logger = logging.getLogger(__name__)


class FillModelError(ValueError):
    """Raised when fills cannot be generated."""


@dataclass(frozen=True)
class FillArtifacts:
    fills: pd.DataFrame
    fills_hash: str
    gap_stats: Dict[str, float | int] | None = None


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


def _coerce_bars_with_timestamp(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        return None
    bars = df.copy()
    if "timestamp" in bars.columns:
        bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    elif "ts" in bars.columns:
        bars["timestamp"] = pd.to_datetime(bars["ts"], utc=True, errors="coerce")
    elif isinstance(bars.index, pd.DatetimeIndex):
        idx = bars.index
        if idx.tz is None:
            bars["timestamp"] = pd.to_datetime(idx, utc=True, errors="coerce")
        else:
            bars["timestamp"] = idx.tz_convert("UTC")
    else:
        return None
    bars = bars.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    for col in ("open", "high", "low", "close"):
        if col not in bars.columns:
            return None
    return bars


def _resolve_same_bar_with_m1(
    *,
    m1_bars: pd.DataFrame,
    trigger_bar_ts: pd.Timestamp,
    trigger_bar_end_ts: pd.Timestamp,
    side: str,
    entry_price: float,
    stop_price: float,
    tp_price: float,
) -> str:
    probe = m1_bars[
        (m1_bars["timestamp"] >= trigger_bar_ts)
        & (m1_bars["timestamp"] < trigger_bar_end_ts)
    ]
    if probe.empty:
        return "missing_m1"

    in_position = False
    for _, row in probe.iterrows():
        high = float(row["high"])
        low = float(row["low"])
        if not in_position:
            if side == "BUY":
                entry_hit = high >= entry_price
            else:
                entry_hit = low <= entry_price
            if not entry_hit:
                continue
            in_position = True

            # Entry minute is sequence-ambiguous if entry and any exit level are reachable
            # inside the same 1m bar.
            if side == "BUY":
                sl_hit = low <= stop_price
                tp_hit = high >= tp_price
            else:
                sl_hit = high >= stop_price
                tp_hit = low <= tp_price
            if sl_hit or tp_hit:
                return "entry_minute_ambiguous"
            continue

        if side == "BUY":
            sl_hit = low <= stop_price
            tp_hit = high >= tp_price
        else:
            sl_hit = high >= stop_price
            tp_hit = low <= tp_price
        if sl_hit and tp_hit:
            return "ambiguous"
        if sl_hit:
            return "sl_first"
        if tp_hit:
            return "tp_first"
    return "ambiguous"


def generate_fills(
    events_intent: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    order_validity_policy: str | None = None,
    session_timezone: str | None = None,
    session_filter: list[str] | None = None,
    allow_same_bar_exit: bool = False,
    same_bar_resolution_mode: str = "no_fill",
    intrabar_probe_bars_m1: Optional[pd.DataFrame] = None,
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
        return FillArtifacts(fills=fills, fills_hash=fills_hash, gap_stats=None)
    if bars.empty:
        raise FillModelError("bars empty; cannot generate fills")

    bars = bars.copy()
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True)
    bars = bars.sort_values("timestamp").reset_index(drop=True)
    m1_probe = _coerce_bars_with_timestamp(intrabar_probe_bars_m1)
    bar_idx = bars.set_index("timestamp")
    rows: List[Dict] = []
    session_end_snap_count = 0
    same_bar_entry_minute_ambiguous_count = 0
    diffs = bars["timestamp"].diff().dt.total_seconds().dropna()
    median_step_s = float(diffs.median()) if len(diffs) else None
    gap_max_s = float(diffs.max()) if len(diffs) else 0.0
    gap_count_gt_2x_median = (
        int((diffs > (2 * median_step_s)).sum()) if median_step_s else 0
    )

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
        stop_price_f = float(stop_price)
        tp_price_f = float(tp_price)

        same_bar_candidate = False
        same_bar_result = "not_applicable"
        same_bar_exit_row = None
        if allow_same_bar_exit:
            if side == "BUY":
                same_stop_hit = float(trigger_bar["low"]) <= stop_price_f
                same_tp_hit = float(trigger_bar["high"]) >= tp_price_f
            else:
                same_stop_hit = float(trigger_bar["high"]) >= stop_price_f
                same_tp_hit = float(trigger_bar["low"]) <= tp_price_f
            same_bar_candidate = bool(same_stop_hit and same_tp_hit)
            if same_bar_candidate:
                if same_bar_resolution_mode == "legacy":
                    same_bar_result = "sl_first"
                    same_bar_exit_row = {
                        "template_id": intent["template_id"],
                        "symbol": intent.get("symbol", "UNKNOWN"),
                        "fill_ts": trigger_bar["timestamp"],
                        "fill_price": stop_price_f,
                        "reason": "stop_loss",
                    }
                elif same_bar_resolution_mode == "m1_probe_then_no_fill":
                    next_rows = bars[bars["timestamp"] > trigger_bar["timestamp"]]["timestamp"]
                    trigger_end = next_rows.iloc[0] if not next_rows.empty else trigger_bar["timestamp"] + pd.Timedelta(minutes=1)
                    if m1_probe is None:
                        same_bar_result = "missing_m1"
                    else:
                        same_bar_result = _resolve_same_bar_with_m1(
                            m1_bars=m1_probe,
                            trigger_bar_ts=trigger_bar["timestamp"],
                            trigger_bar_end_ts=trigger_end,
                            side=side,
                            entry_price=float(trigger_level),
                            stop_price=stop_price_f,
                            tp_price=tp_price_f,
                        )
                    if same_bar_result == "entry_minute_ambiguous":
                        same_bar_entry_minute_ambiguous_count += 1
                    if same_bar_result == "tp_first":
                        same_bar_exit_row = {
                            "template_id": intent["template_id"],
                            "symbol": intent.get("symbol", "UNKNOWN"),
                            "fill_ts": trigger_bar["timestamp"],
                            "fill_price": tp_price_f,
                            "reason": "take_profit",
                        }
                    elif same_bar_result == "sl_first":
                        same_bar_exit_row = {
                            "template_id": intent["template_id"],
                            "symbol": intent.get("symbol", "UNKNOWN"),
                            "fill_ts": trigger_bar["timestamp"],
                            "fill_price": stop_price_f,
                            "reason": "stop_loss",
                        }
                else:
                    same_bar_result = "ambiguous"

                if same_bar_exit_row is None:
                    # Remove pre-added entry/cancel rows for this group: ambiguous same-bar means no entry fill.
                    rows = [
                        r
                        for r in rows
                        if not (
                            r.get("oco_group_id") == oco_group_id
                            and r.get("template_id") == intent.get("template_id")
                            and r.get("reason") == "signal_fill"
                        )
                    ]
                    rows = [
                        r
                        for r in rows
                        if not (
                            r.get("oco_group_id") == oco_group_id
                            and r.get("reason") == "order_cancelled_oco"
                        )
                    ]
                    logger.info(
                        "actions: same_bar_resolution template_id=%s symbol=%s same_bar_candidate=%s resolution_mode=%s m1_probe_result=%s final_decision=%s",
                        intent.get("template_id"),
                        symbol,
                        same_bar_candidate,
                        same_bar_resolution_mode,
                        same_bar_result,
                        "order_ambiguous_no_fill",
                    )
                    rows.append(
                        {
                            "template_id": intent["template_id"],
                            "symbol": symbol,
                            "fill_ts": trigger_bar["timestamp"],
                            "fill_price": float("nan"),
                            "reason": "order_ambiguous_no_fill",
                            "side": side,
                            "oco_group_id": oco_group_id,
                            "cancel_reason": "entry_minute_ambiguous"
                            if same_bar_result == "entry_minute_ambiguous"
                            else "same_bar_ambiguous",
                        }
                    )
                    continue

        logger.info(
            "actions: same_bar_resolution template_id=%s symbol=%s same_bar_candidate=%s resolution_mode=%s m1_probe_result=%s final_decision=%s",
            intent.get("template_id"),
            symbol,
            same_bar_candidate,
            same_bar_resolution_mode,
            same_bar_result,
            same_bar_exit_row["reason"] if same_bar_exit_row else "next_bar_scan",
        )
        valid_to = _valid_to_for(intent, signal_ts)
        if allow_same_bar_exit:
            scan = bars[
                (bars["timestamp"] >= trigger_bar["timestamp"])
                & (bars["timestamp"] <= valid_to)
            ]
        else:
            scan = bars[
                (bars["timestamp"] > trigger_bar["timestamp"])
                & (bars["timestamp"] <= valid_to)
            ]
        exit_row = same_bar_exit_row
        for _, bar_row in scan.iterrows():
            if exit_row is not None:
                break
            bar_ts = bar_row["timestamp"]
            if side == "BUY":
                stop_hit = float(bar_row["low"]) <= stop_price_f
                tp_hit = float(bar_row["high"]) >= tp_price_f
            else:  # SELL
                stop_hit = float(bar_row["high"]) >= stop_price_f
                tp_hit = float(bar_row["low"]) <= tp_price_f
            if stop_hit and tp_hit:
                exit_row = {
                    "template_id": intent["template_id"],
                    "symbol": intent.get("symbol", "UNKNOWN"),
                    "fill_ts": bar_ts,
                    "fill_price": stop_price_f,
                    "reason": "stop_loss",
                }
                break
            if stop_hit:
                exit_row = {
                    "template_id": intent["template_id"],
                    "symbol": intent.get("symbol", "UNKNOWN"),
                    "fill_ts": bar_ts,
                    "fill_price": stop_price_f,
                    "reason": "stop_loss",
                }
                break
            if tp_hit:
                exit_row = {
                    "template_id": intent["template_id"],
                    "symbol": intent.get("symbol", "UNKNOWN"),
                    "fill_ts": bar_ts,
                    "fill_price": tp_price_f,
                    "reason": "take_profit",
                }
                break
        if exit_row is None:
            requested_valid_to = valid_to
            if requested_valid_to in bar_idx.index:
                effective_valid_to = requested_valid_to
            else:
                idx = bar_idx.index.searchsorted(requested_valid_to, side="right") - 1
                if idx < 0:
                    raise FillModelError(
                        "session_end exit: no bar <= valid_to. "
                        f"template_id={intent.get('template_id')} symbol={symbol} "
                        f"valid_to={requested_valid_to} min_ts={bar_idx.index.min()} max_ts={bar_idx.index.max()}"
                    )
                effective_valid_to = bar_idx.index[idx]
                session_end_snap_count += 1
                gap_s = int((requested_valid_to - effective_valid_to).total_seconds())
                logger.info(
                    "actions: session_end_snap_valid_to template_id=%s symbol=%s requested=%s effective=%s gap_s=%s",
                    intent.get("template_id"),
                    symbol,
                    requested_valid_to,
                    effective_valid_to,
                    gap_s,
                )
            exit_bar = bar_idx.loc[effective_valid_to]
            exit_row = {
                "template_id": intent["template_id"],
                "symbol": intent.get("symbol", "UNKNOWN"),
                "fill_ts": effective_valid_to,
                "fill_price": float(exit_bar["close"]),
                "reason": "session_end",
            }
            if requested_valid_to != effective_valid_to:
                exit_row["dbg_valid_to_requested_ts"] = requested_valid_to
                exit_row["dbg_valid_to_effective_ts"] = effective_valid_to
                exit_row["dbg_valid_to_gap_seconds"] = int(
                    (requested_valid_to - effective_valid_to).total_seconds()
                )
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
        return FillArtifacts(fills=fills, fills_hash=fills_hash, gap_stats=None)

    fills_hash = _hash_dataframe(fills)
    logger.info("actions: fills_generated fills_hash=%s fills=%d", fills_hash, len(fills))
    if same_bar_entry_minute_ambiguous_count:
        logger.info(
            "actions: same_bar_entry_minute_ambiguous_count count=%d",
            same_bar_entry_minute_ambiguous_count,
        )
    gap_stats = {
        "bars_gap_median_seconds": median_step_s if median_step_s is not None else 0.0,
        "bars_gap_max_seconds": gap_max_s,
        "bars_gap_count_gt_2x_median": gap_count_gt_2x_median,
        "session_end_snap_count": session_end_snap_count,
    }
    return FillArtifacts(fills=fills, fills_hash=fills_hash, gap_stats=gap_stats)
