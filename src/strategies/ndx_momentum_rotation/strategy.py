"""Entrypoint for ndx_momentum_rotation strategy skeleton."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyDefinition:
    strategy_id: str
    description: str


def build_strategy() -> StrategyDefinition:
    return StrategyDefinition(
        strategy_id="ndx_momentum_rotation",
        description="NDX100 monthly momentum rotation (skeleton)",
    )
