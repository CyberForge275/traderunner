"""Regime filter interface and baseline skeleton implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd


class StrategyRegimeFilter(Protocol):
    name: str

    def evaluate(self, bars: pd.DataFrame) -> pd.DataFrame:
        ...


@dataclass(frozen=True)
class QqqSma200RegimeFilter:
    name: str = "qqq_sma200"

    def evaluate(self, bars: pd.DataFrame) -> pd.DataFrame:
        if "timestamp" not in bars.columns:
            raise ValueError("bars must include timestamp for regime evaluation")
        ts = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
        if ts.isna().any():
            raise ValueError("invalid timestamp values for regime evaluation")

        return pd.DataFrame(
            {
                "timestamp": ts,
                "regime_on": True,
                "regime_reason": "SKELETON_PLACEHOLDER",
            }
        )


def build_regime_filter(name: str) -> StrategyRegimeFilter:
    if name == "qqq_sma200":
        return QqqSma200RegimeFilter()
    if name in {"sp500_sma200", "breadth_ema_cross"}:
        raise NotImplementedError(
            f"regime filter {name!r} not implemented in skeleton"
        )
    raise ValueError(f"unknown regime_filter: {name!r}")
