"""Trading strategies package.

This module exposes core strategy interfaces and a small hook registry for
strategy-specific pipeline extensions (e.g. two-stage daily scan).
"""

from collections.abc import Callable
from typing import Any, Dict, Optional

from .base import IStrategy, Signal, StrategyConfig
from .registry import registry


DailyScanHook = Callable[[Any, int], list[str]]  # (pipeline, max_daily) -> symbols


class StrategyHooks:
    """Registry for optional strategy-specific pipeline hooks.

    This keeps the central pipeline generic and lets complex strategies
    register their own behavior without hard-coding strategy names.
    """

    def __init__(self) -> None:
        self._daily_scan: Dict[str, DailyScanHook] = {}

    def register_daily_scan(self, strategy_name: str, hook: DailyScanHook) -> None:
        self._daily_scan[strategy_name] = hook

    def get_daily_scan(self, strategy_name: str) -> Optional[DailyScanHook]:
        return self._daily_scan.get(strategy_name)


strategy_hooks = StrategyHooks()


__all__ = [
    "IStrategy",
    "Signal",
    "StrategyConfig",
    "registry",
    "strategy_hooks",
    "DailyScanHook",
]
