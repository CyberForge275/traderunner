"""Portfolio allocation interface for momentum rotation (skeleton)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd


class PortfolioAllocator(Protocol):
    def target_weights(
        self,
        *,
        topk_symbols: list[str],
        current_positions: pd.DataFrame,
        risk_off_mode: str,
        cash_policy: str,
    ) -> pd.DataFrame:
        ...


@dataclass(frozen=True)
class EqualWeightAllocator:
    def target_weights(
        self,
        *,
        topk_symbols: list[str],
        current_positions: pd.DataFrame,
        risk_off_mode: str,
        cash_policy: str,
    ) -> pd.DataFrame:
        if not topk_symbols:
            return pd.DataFrame(columns=["symbol", "target_weight"])
        weight = 1.0 / float(len(topk_symbols))
        return pd.DataFrame({"symbol": sorted(topk_symbols), "target_weight": weight})


def build_allocator(sizing_mode: str) -> PortfolioAllocator:
    if sizing_mode == "EQUAL_WEIGHT":
        return EqualWeightAllocator()
    if sizing_mode == "FIXED_NOTIONAL":
        raise NotImplementedError("FIXED_NOTIONAL allocator not implemented in skeleton")
    raise ValueError(f"unknown sizing_mode: {sizing_mode!r}")
