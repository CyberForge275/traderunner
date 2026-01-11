"""Strategy Helpers - Dashboard utilities for strategy metadata access.

This module provides centralized access to the StrategyRegistry from
src.strategies.metadata (SSOT).
Utility functions for strategy management in trading dashboard.
"""

from src.strategies.metadata import StrategyRegistry
from strategies.factory import list_strategies


# Compatibility alias for architecture tests
def get_available_strategies():
    """Get list of available strategy names.
    
    Note: This is a compatibility alias for list_strategies().
    New code should use list_strategies() directly.
    """
    return list_strategies()


def get_registry() -> StrategyRegistry:
    """Get the central StrategyRegistry instance.
    
    Returns:
        StrategyRegistry singleton instance
    """
    return StrategyRegistry()
