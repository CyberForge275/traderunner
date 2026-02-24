from __future__ import annotations


def entry_levels(*, entry_mode: str, levels: dict[str, float]) -> tuple[float, float]:
    if entry_mode == "mother_bar":
        return levels["mother_high"], levels["mother_low"]
    return levels["ib_high"], levels["ib_low"]


def capped_risk_levels(
    *,
    side: str,
    entry: float,
    structure_stop: float,
    atr_value: float,
    stop_cap_atr: float,
    risk_reward_ratio: float,
) -> tuple[float, float, float, float, float, bool]:
    risk_raw = (entry - structure_stop) if side == "BUY" else (structure_stop - entry)
    if risk_raw <= 0:
        raise ValueError("non_positive_risk")
    risk_cap = float(stop_cap_atr) * float(atr_value)
    if risk_cap <= 0:
        raise ValueError("non_positive_risk_cap")
    risk_eff = min(risk_raw, risk_cap)
    sl_was_capped = risk_raw > risk_cap
    stop_loss = entry - risk_eff if side == "BUY" else entry + risk_eff
    take_profit = entry + (risk_eff * risk_reward_ratio) if side == "BUY" else entry - (risk_eff * risk_reward_ratio)
    return stop_loss, take_profit, risk_raw, risk_cap, risk_eff, sl_was_capped
