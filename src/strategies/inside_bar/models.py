from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import pandas as pd


@dataclass
class RawSignal:
    """
    Raw signal output from core (format-agnostic).

    This is converted to specific formats by adapters:
    - Backtest: Signal object
    - Live: SignalOutputSpec
    """
    timestamp: pd.Timestamp
    side: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate signal data."""
        assert self.side in ["BUY", "SELL"], f"Invalid side: {self.side}"
        assert self.entry_price > 0, "Entry price must be positive"
        assert self.stop_loss > 0, "Stop loss must be positive"
        assert self.take_profit > 0, "Take profit must be positive"

        if self.side == "BUY":
            assert self.stop_loss < self.entry_price, \
                "BUY: Stop loss must be below entry"
            assert self.take_profit > self.entry_price, \
                "BUY: Take profit must be above entry"
        else:  # SELL
            assert self.stop_loss > self.entry_price, \
                "SELL: Stop loss must be above entry"
            assert self.take_profit < self.entry_price, \
                "SELL: Take profit must be below entry"
