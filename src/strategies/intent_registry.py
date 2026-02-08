"""Strategy intent adapter registry (pipeline-neutral)."""

from __future__ import annotations

from typing import Protocol

from .registry import get_strategy, StrategyPlugin


class StrategyIntentAdapter(StrategyPlugin, Protocol):
    """Strategy adapter interface for intent generation (strategy-owned)."""

    def generate_intent(self, signals_frame, strategy_id: str, strategy_version: str, params: dict):
        ...


def get_strategy_adapter(strategy_id: str) -> StrategyIntentAdapter:
    """Return a strategy adapter by id (strategy-owned)."""
    return get_strategy(strategy_id)  # type: ignore[return-value]
