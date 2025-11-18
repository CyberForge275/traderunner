from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING, ROUND_FLOOR
from typing import Literal, Optional

RoundMode = Literal["nearest", "floor", "ceil"]


def _D(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def qty_fixed(qty: float | int, *, min_qty: int = 1) -> int:
    quantity = max(int(qty), 0)
    if quantity == 0:
        return 0
    return max(quantity, min_qty if min_qty > 0 else 0)


def qty_pct_of_equity(equity: float, pct: float, price: float, *, min_qty: int = 1) -> int:
    e = _D(equity)
    p = _D(pct) / Decimal("100")
    price_dec = _D(price)
    if e <= 0 or p <= 0 or price_dec <= 0:
        return 0
    raw = (e * p) / price_dec
    qty = int(raw.to_integral_value(rounding=ROUND_FLOOR))
    if qty <= 0:
        return 0
    return max(qty, min_qty)


def qty_risk_based(
    *,
    entry_price: float | None = None,
    stop_price: float | None = None,
    equity: float | None = None,
    risk_pct: float | None = None,
    tick_size: float | None = None,
    round_mode: RoundMode = "nearest",
    min_qty: int = 1,
    max_notional: Optional[float] = None,
) -> int:
    if entry_price is None or stop_price is None or equity is None or risk_pct is None:
        return 0

    entry = _D(entry_price)
    stop = _D(stop_price)
    equity_dec = _D(equity)
    pct = _D(risk_pct) / Decimal("100")

    diff = abs(entry - stop)
    if diff <= 0 or equity_dec <= 0 or pct <= 0:
        return 0

    risk_cash = equity_dec * pct
    qty = risk_cash / diff

    rounding = {
        "nearest": ROUND_HALF_UP,
        "floor": ROUND_FLOOR,
        "ceil": ROUND_CEILING,
    }.get(round_mode, ROUND_HALF_UP)

    qty_int = int(qty.to_integral_value(rounding=rounding))
    if qty_int <= 0:
        return 0

    if min_qty > 0 and qty_int < min_qty:
        qty_int = min_qty

    if max_notional is not None and entry > 0:
        cap = int((Decimal(str(max_notional)) / entry).to_integral_value(rounding=ROUND_FLOOR))
        if cap < min_qty:
            return 0
        qty_int = min(qty_int, cap)

    return qty_int
