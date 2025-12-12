"""
Strategy Helper Utilities - UPDATED to use Central Registry
============================================================

Helper functions for accessing strategy metadata.
Now uses src.strategies.metadata.StrategyRegistry as Single Source of Truth.
"""

from typing import Dict, Optional
from src.strategies.metadata import StrategyRegistry, StrategyMetadata
from src.strategies.profiles import (
    INSIDE_BAR_V1_PROFILE,
    INSIDE_BAR_V2_PROFILE,
    RUDOMETKIN_MOC_PROFILE,
)


# Initialize registry with profiles on module load
_registry = StrategyRegistry()

# Register all known strategies
for profile in [INSIDE_BAR_V1_PROFILE, INSIDE_BAR_V2_PROFILE, RUDOMETKIN_MOC_PROFILE]:
    if not _registry.exists(profile.strategy_id):
        _registry.register(profile)


def get_registry() -> StrategyRegistry:
    """
    Get the central StrategyRegistry instance.
    
    Returns:
        StrategyRegistry singleton
    """
    return _registry


def get_strategy_metadata(strategy_id: str) -> Optional[StrategyMetadata]:
    """
    Get strategy metadata by ID.
    
    Args:
        strategy_id: Strategy identifier
        
    Returns:
        StrategyMetadata or None if not found
    """
    return _registry.get_or_none(strategy_id)


def get_all_strategies() -> Dict[str, StrategyMetadata]:
    """
    Get all registered strategies as dict.
    
    Returns:
        Dictionary mapping strategy_id to StrategyMetadata
    """
    return {meta.strategy_id: meta for meta in _registry.list_all()}


def get_strategy_display_names() -> Dict[str, str]:
    """
    Get mapping of strategy_id to display_name.
    
    Returns:
        Dictionary mapping strategy_id to display_name
    """
    return {meta.strategy_id: meta.display_name for meta in _registry.list_all()}


def get_live_capable_strategies() -> Dict[str, StrategyMetadata]:
    """
    Get strategies that support live trading.
    
    Returns:
        Dictionary of live-capable strategies
    """
    live_strategies = _registry.get_by_capability(
        lambda cap: cap.supports_live_trading
    )
    return {meta.strategy_id: meta for meta in live_strategies}


def get_backtest_capable_strategies() -> Dict[str, StrategyMetadata]:
    """
    Get strategies that support backtesting.
    
    Returns:
        Dictionary of backtest-capable strategies
    """
    backtest_strategies = _registry.get_by_capability(
        lambda cap: cap.supports_backtest
    )
    return {meta.strategy_id: meta for meta in backtest_strategies}


def get_pre_papertrade_capable_strategies() -> Dict[str, StrategyMetadata]:
    """
    Get strategies that support pre-papertrading.
    
    Returns:
        Dictionary of pre-papertrade-capable strategies
    """
    pre_paper_strategies = _registry.get_by_capability(
        lambda cap: cap.supports_pre_papertrade
    )
    return {meta.strategy_id: meta for meta in pre_paper_strategies}
