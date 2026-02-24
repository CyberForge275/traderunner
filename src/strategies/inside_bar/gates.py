from __future__ import annotations

from typing import Any


def evaluate_deviation_gate(
    *,
    max_dev_atr: float | None,
    atr_for_deviation: float,
    reference_price: float,
    entry_long: float,
    entry_short: float,
    idx: int,
) -> tuple[bool, bool, float, float, float, float, list[dict[str, Any]]]:
    allow_long = True
    allow_short = True
    long_dev_abs = abs(entry_long - reference_price)
    short_dev_abs = abs(entry_short - reference_price)
    long_dev_atr = float("inf")
    short_dev_atr = float("inf")
    reject_events: list[dict[str, Any]] = []

    if max_dev_atr is None:
        return (
            allow_long,
            allow_short,
            long_dev_abs,
            short_dev_abs,
            long_dev_atr,
            short_dev_atr,
            reject_events,
        )

    if atr_for_deviation <= 0:
        allow_long = False
        allow_short = False
        reject_events.append(
            {
                "event": "signal_rejected",
                "reason": "MAX_DEVIATION_ATR",
                "detail": "atr_non_positive",
                "idx": int(idx),
                "atr": atr_for_deviation,
            }
        )
        return (
            allow_long,
            allow_short,
            long_dev_abs,
            short_dev_abs,
            long_dev_atr,
            short_dev_atr,
            reject_events,
        )

    max_dev_abs = float(max_dev_atr) * atr_for_deviation
    long_dev_atr = long_dev_abs / atr_for_deviation
    short_dev_atr = short_dev_abs / atr_for_deviation

    if long_dev_abs > max_dev_abs:
        allow_long = False
        reject_events.append(
            {
                "event": "signal_rejected",
                "reason": "MAX_DEVIATION_ATR",
                "side": "BUY",
                "idx": int(idx),
                "deviation_abs": long_dev_abs,
                "deviation_atr": long_dev_atr,
                "max_allowed_atr": float(max_dev_atr),
            }
        )
    if short_dev_abs > max_dev_abs:
        allow_short = False
        reject_events.append(
            {
                "event": "signal_rejected",
                "reason": "MAX_DEVIATION_ATR",
                "side": "SELL",
                "idx": int(idx),
                "deviation_abs": short_dev_abs,
                "deviation_atr": short_dev_atr,
                "max_allowed_atr": float(max_dev_atr),
            }
        )

    return (
        allow_long,
        allow_short,
        long_dev_abs,
        short_dev_abs,
        long_dev_atr,
        short_dev_atr,
        reject_events,
    )
