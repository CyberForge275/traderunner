from __future__ import annotations

from typing import Any


def build_signal_metadata(
    *,
    session_key: tuple,
    ib_idx: int | None,
    entry_mode: str,
    sl_was_capped: bool,
    risk_raw: float,
    risk_cap: float,
    risk_eff: float,
    mother_high: float,
    mother_low: float,
    atr: float,
    symbol: str,
    deviation_abs: float | None = None,
    deviation_atr: float | None = None,
    mother_body_fraction: float | None = None,
    inside_body_fraction: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "pattern": "inside_bar_breakout",
        "session_key": str(session_key),
        "ib_idx": ib_idx,
        "entry_mode": entry_mode,
        "stop_cap_applied": sl_was_capped,
        "initial_risk": risk_raw,
        "effective_risk": risk_eff,
        "risk_raw": risk_raw,
        "risk_cap": risk_cap,
        "risk_eff": risk_eff,
        "sl_was_capped": sl_was_capped,
        "cap_mode": "atr",
        "mother_high": mother_high,
        "mother_low": mother_low,
        "atr": atr,
        "symbol": symbol,
    }
    if deviation_abs is not None:
        metadata["deviation_abs"] = deviation_abs
    if deviation_atr is not None:
        metadata["deviation_atr"] = deviation_atr
    if mother_body_fraction is not None:
        metadata["mother_body_fraction"] = mother_body_fraction
    if inside_body_fraction is not None:
        metadata["inside_body_fraction"] = inside_body_fraction
    if extra:
        metadata.update(extra)
    return metadata
