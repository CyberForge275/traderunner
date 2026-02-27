"""Intent generation for harami_break strategy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd

from axiom_bt.artifacts.intent_contract import sanitize_intent
from trade.session_windows import parse_session_filter


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


def _session_window_key(
    signal_ts_utc: pd.Timestamp,
    *,
    session_timezone: str,
    session_windows: list[str],
) -> tuple[str, int] | None:
    local_ts = pd.to_datetime(signal_ts_utc, utc=True).tz_convert(session_timezone)
    t = local_ts.timetz().replace(tzinfo=None)
    windows = parse_session_filter(session_windows)
    for idx, window in enumerate(windows):
        if window.start <= t <= window.end:
            return (local_ts.date().isoformat(), idx)
    return None


def generate_intent(
    signals_frame: pd.DataFrame,
    strategy_id: str,
    strategy_version: str,
    params: dict,
) -> IntentArtifacts:
    if signals_frame.empty:
        return IntentArtifacts(
            signals_frame=signals_frame,
            events_intent=pd.DataFrame(),
            intent_hash=_hash_dataframe(pd.DataFrame()),
        )

    required_params = [
        "session_timezone",
        "session_windows",
        "max_trades_per_session_window",
        "order_validity_policy",
    ]
    missing_params = [k for k in required_params if k not in params]
    if missing_params:
        raise ValueError(
            f"harami_break generate_intent missing required params: {', '.join(sorted(missing_params))}"
        )

    required_cols = [
        "timestamp",
        "symbol",
        "armed",
        "valid_window_ok",
        "armed_from_ts",
        "valid_until_ts",
        "long_trigger_price",
        "short_trigger_price",
        "mother_bar_high",
        "mother_bar_low",
    ]
    missing_cols = [c for c in required_cols if c not in signals_frame.columns]
    if missing_cols:
        raise ValueError(
            f"harami_break signals_frame missing columns: {', '.join(sorted(missing_cols))}"
        )

    filtered = signals_frame.copy()
    filtered["timestamp"] = pd.to_datetime(filtered["timestamp"], utc=True, errors="coerce")
    filtered["armed_from_ts"] = pd.to_datetime(filtered["armed_from_ts"], utc=True, errors="coerce")
    filtered["valid_until_ts"] = pd.to_datetime(filtered["valid_until_ts"], utc=True, errors="coerce")
    filtered = filtered.sort_values("timestamp").reset_index(drop=True)
    filtered = filtered[
        filtered["armed"].fillna(False).astype(bool)
        & filtered["valid_window_ok"].fillna(False).astype(bool)
        & filtered["armed_from_ts"].notna()
        & filtered["valid_until_ts"].notna()
    ]

    if filtered.empty:
        events = pd.DataFrame(
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
        events = _canonicalize_events_intent(events)
        return IntentArtifacts(signals_frame=signals_frame, events_intent=events, intent_hash=_hash_dataframe(events))

    max_trades = int(params["max_trades_per_session_window"])
    session_timezone = str(params["session_timezone"])
    session_windows = list(params["session_windows"])
    validity_reason = str(params["order_validity_policy"])

    trade_count_by_window: dict[tuple[str, int], int] = {}
    intents: list[dict] = []
    for _, row in filtered.iterrows():
        signal_ts = pd.to_datetime(row["timestamp"], utc=True)
        window_key = _session_window_key(
            signal_ts,
            session_timezone=session_timezone,
            session_windows=session_windows,
        )
        if window_key is None:
            continue
        if trade_count_by_window.get(window_key, 0) >= max_trades:
            continue

        symbol = str(row["symbol"])
        base_template_id = f"hb_{symbol}_{signal_ts.strftime('%Y%m%d_%H%M%S')}"
        oco_group_id = (
            f"{symbol}_{signal_ts.isoformat()}_{strategy_id}_{strategy_version}_{base_template_id}"
        )
        valid_from = pd.to_datetime(row["armed_from_ts"], utc=True)
        valid_to = pd.to_datetime(row["valid_until_ts"], utc=True)

        long_entry = row.get("long_trigger_price")
        short_entry = row.get("short_trigger_price")
        mother_high = row.get("mother_bar_high")
        mother_low = row.get("mother_bar_low")

        legs: list[dict] = []
        if pd.notna(long_entry) and pd.notna(mother_low):
            entry = float(long_entry)
            stop = float(mother_low)
            risk = entry - stop
            if risk > 0:
                legs.append(
                    {
                        "template_id": f"{base_template_id}_BUY",
                        "side": "BUY",
                        "entry_price": entry,
                        "stop_price": stop,
                        "take_profit_price": entry + risk,
                    }
                )

        if pd.notna(short_entry) and pd.notna(mother_high):
            entry = float(short_entry)
            stop = float(mother_high)
            risk = stop - entry
            if risk > 0:
                legs.append(
                    {
                        "template_id": f"{base_template_id}_SELL",
                        "side": "SELL",
                        "entry_price": entry,
                        "stop_price": stop,
                        "take_profit_price": entry - risk,
                    }
                )

        if not legs:
            continue

        for leg in legs:
            raw_intent = {
                "template_id": leg["template_id"],
                "signal_ts": signal_ts,
                "symbol": symbol,
                "side": leg["side"],
                "entry_price": leg["entry_price"],
                "stop_price": leg["stop_price"],
                "take_profit_price": leg["take_profit_price"],
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "oco_group_id": oco_group_id,
                "order_valid_to_ts": valid_to,
                "order_valid_to_reason": validity_reason,
                "dbg_valid_from_ts_utc": valid_from,
                "dbg_valid_to_ts_utc": valid_to,
                "dbg_signal_ts_ny": signal_ts.tz_convert("America/New_York"),
                "dbg_signal_ts_berlin": signal_ts.tz_convert("Europe/Berlin"),
            }
            intents.append(
                sanitize_intent(
                    raw_intent,
                    intent_generated_ts=signal_ts,
                    strict=bool(params.get("strict_intent_contract", False)),
                    run_id=params.get("run_id"),
                    template_id=raw_intent["template_id"],
                )
            )

        trade_count_by_window[window_key] = trade_count_by_window.get(window_key, 0) + 1

    events_intent = pd.DataFrame(intents)
    events_intent = _canonicalize_events_intent(events_intent)
    return IntentArtifacts(
        signals_frame=signals_frame,
        events_intent=events_intent,
        intent_hash=_hash_dataframe(events_intent),
    )
