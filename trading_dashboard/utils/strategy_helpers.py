"""Strategy Helpers - Dashboard utilities for strategy metadata access.

This module provides centralized access to the StrategyRegistry from
src.strategies.metadata (SSOT).
"""

from src.strategies.metadata import StrategyRegistry


def get_registry() -> StrategyRegistry:
    """Get the central StrategyRegistry instance.
    
    Returns:
        StrategyRegistry singleton instance
    """
    return StrategyRegistry()
