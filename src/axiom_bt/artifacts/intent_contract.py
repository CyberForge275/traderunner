"""Intent contract (SSOT) for events_intent.csv.

Intent is a snapshot at signal time (end of inside bar). No trigger/fill/trade
outcomes allowed. Scheduled validity is allowed only with explicit naming.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping

import pandas as pd

logger = logging.getLogger(__name__)

# Explicitly allowed columns (base). Prefixes are handled separately.
INTENT_ALLOWED_COLUMNS: set[str] = {
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
    "breakout_confirmation",
    "order_valid_to_ts",
    "order_valid_to_reason",
    "dbg_signal_ts_ny",
    "dbg_signal_ts_berlin",
    "dbg_effective_valid_from_policy",
    "dbg_valid_from_ts_utc",
    "dbg_valid_from_ts",
    "dbg_valid_from_ts_ny",
    "dbg_valid_to_ts_utc",
    "dbg_valid_to_ts_ny",
    "dbg_valid_to_ts",
    "dbg_breakout_level",
    "dbg_mother_high",
    "dbg_mother_low",
    "dbg_mother_range",
    "dbg_mother_ts",
    "dbg_inside_ts",
    "dbg_order_expired",
    "dbg_order_expire_reason",
}

# Forbidden columns (exact)
INTENT_FORBIDDEN_COLUMNS: set[str] = {
    "exit_ts",
    "exit_reason",
    "dbg_exit_ts_ny",
    "dbg_trigger_ts",
}

# Prefix-based forbidden (future outcomes)
INTENT_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "fill_",
    "pnl",
    "realized_",
    "trade_",
)

# Prefix-based allowed (signal snapshot from strategy)
INTENT_ALLOWED_PREFIXES: tuple[str, ...] = (
    "sig_",
)

# Allowed scheduled validity fields for timestamp purity checks
INTENT_ALLOWED_SCHEDULED_VALIDITY: set[str] = {
    "order_valid_to_ts",
    "dbg_valid_to_ts_utc",
    "dbg_valid_to_ts_ny",
    "dbg_valid_to_ts",
}


def _is_forbidden_key(key: str) -> bool:
    if key in INTENT_FORBIDDEN_COLUMNS:
        return True
    return key.startswith(INTENT_FORBIDDEN_PREFIXES)


def _is_allowed_key(key: str) -> bool:
    if key in INTENT_ALLOWED_COLUMNS:
        return True
    return key.startswith(INTENT_ALLOWED_PREFIXES)


def sanitize_intent(
    intent: Mapping[str, Any],
    *,
    intent_generated_ts: pd.Timestamp | None,
    strict: bool = False,
    run_id: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    """Return sanitized intent dict per SSOT contract.

    - Drops forbidden columns.
    - Leaves only allowed columns and allowed prefixes.
    - Enforces timestamp purity when strict=True.
    """
    removed: list[str] = []
    kept: list[str] = []
    out: dict[str, Any] = {}

    for key, value in intent.items():
        if _is_forbidden_key(key):
            removed.append(key)
            continue
        if _is_allowed_key(key):
            out[key] = value
            kept.append(key)
            continue
        # Unknown keys are dropped (contract hardening)
        removed.append(key)

    if removed:
        logger.error(
            "actions: intent_contract_violation run_id=%s template_id=%s removed=%s",
            run_id,
            template_id,
            removed,
        )
        if strict:
            raise ValueError(f"intent_contract_violation removed={removed}")

    if intent_generated_ts is not None:
        intent_ts = pd.to_datetime(intent_generated_ts, utc=True)
        for key, value in out.items():
            if "ts" not in key:
                continue
            if key in INTENT_ALLOWED_SCHEDULED_VALIDITY:
                continue
            try:
                ts_val = pd.to_datetime(value, utc=True)
            except Exception:
                continue
            if pd.notna(ts_val) and ts_val > intent_ts:
                logger.error(
                    "actions: intent_contract_future_ts run_id=%s template_id=%s key=%s value=%s intent_ts=%s",
                    run_id,
                    template_id,
                    key,
                    ts_val,
                    intent_ts,
                )
                if strict:
                    raise ValueError(
                        f"intent_contract_future_ts key={key} value={ts_val} intent_ts={intent_ts}"
                    )

    logger.info(
        "actions: intent_contract_sanitize run_id=%s template_id=%s kept=%d removed=%d",
        run_id,
        template_id,
        len(kept),
        len(removed),
    )
    return out
