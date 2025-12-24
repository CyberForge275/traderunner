from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


DEFAULT_INITIAL_CASH: float = 10_000.0
DEFAULT_RISK_PCT: float = 1.0
DEFAULT_MIN_QTY: int = 1
DEFAULT_FEE_BPS: float = 2.0
DEFAULT_SLIPPAGE_BPS: float = 1.0

INSIDE_BAR_TIMEZONE: str = "Europe/Berlin"
INSIDE_BAR_SESSIONS: List[str] = ["15:00-16:00", "16:00-17:00"]
INSIDE_BAR_DEFAULT_DATA_TZ: str = "Europe/Berlin"


@dataclass(frozen=True)
class StrategyDefaults:
    name: str
    timezone: str
    sessions: List[str]
    costs: Dict[str, float]
    initial_cash: float
    risk_pct: float
    min_qty: int


INSIDE_BAR_DEFAULTS = StrategyDefaults(
    name="insidebar_intraday",
    timezone=INSIDE_BAR_TIMEZONE,
    sessions=INSIDE_BAR_SESSIONS,
    costs={
        "fees_bps": DEFAULT_FEE_BPS,
        "slippage_bps": DEFAULT_SLIPPAGE_BPS,
    },
    initial_cash=DEFAULT_INITIAL_CASH,
    risk_pct=DEFAULT_RISK_PCT,
    min_qty=DEFAULT_MIN_QTY,
)
