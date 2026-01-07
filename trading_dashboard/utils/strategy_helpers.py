"""
Strategy Helpers - Backward Compatibility Stub

This module provides backward-compatible access to strategy metadata
for tests and legacy code. New code should use src/strategies/metadata instead.
"""

from apps.streamlit.state import STRATEGY_REGISTRY


def get_strategy_metadata(strategy_name: str):
    """Get strategy metadata by name.
    
    Args:
        strategy_name: Strategy identifier
        
    Returns:
        StrategyMetadata object or None if not found
    """
    return STRATEGY_REGISTRY.get(strategy_name)


def list_available_strategies():
    """Get list of all available strategy names.
    
    Returns:
        List of strategy identifiers
    """
    return list(STRATEGY_REGISTRY.keys())
