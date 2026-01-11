"""Strategy Helpers - Dashboard utilities for strategy metadata access.

This module provides centralized access to the StrategyRegistry from
src.strategies.metadata (SSOT).
Utility functions for strategy management in trading dashboard.
"""
from typing import Optional, Dict, Any

from src.strategies.metadata import StrategyRegistry, StrategyMetadata
from src.strategies.factory import list_strategies


# Compatibility alias for architecture tests
def get_available_strategies():
    """Get list of available strategy names.
    
    Note: This is a compatibility alias for list_strategies().
    New code should use list_strategies() directly.
    """
    return list_strategies()


def get_registry() -> StrategyRegistry:
    """Get the central StrategyRegistry instance with profiles loaded.
    
    Returns:
        StrategyRegistry singleton instance
    """
    registry = StrategyRegistry()
    _ensure_profiles_registered(registry)
    return registry


def _ensure_profiles_registered(registry: StrategyRegistry):
    """Ensure strategy profiles are registered in the registry."""
    # Only load if registry is empty (minimal approach)
    # In a full system, this would be handled by a discovery service
    if registry.count() > 0:
        return
        
    try:
        from src.strategies import profiles
        for item_name in getattr(profiles, "__all__", []):
            profile = getattr(profiles, item_name)
            if isinstance(profile, StrategyMetadata) and not registry.exists(profile.strategy_id):
                registry.register(profile)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Error registering strategy profiles: {e}")


def get_strategy_default_params(strategy_id: str, version: Optional[str] = None) -> Dict[str, Any]:
    """Get default parameters for a strategy version from SSOT metadata.
    
    Args:
        strategy_id: Strategy identifier (e.g., 'inside_bar')
        version: Optional version string (e.g., '1.0.0')
        
    Returns:
        Dictionary of default parameters or empty dict if not found
    """
    registry = get_registry()
    
    # Map dashboard strategy IDs to canonical names if necessary
    # insidebar_intraday -> inside_bar
    canonical_id = strategy_id.replace("insidebar_intraday", "inside_bar")
    
    try:
        if version:
            # Try to find specific version by canonical name or strategy_id
            strategies = registry.get_by_canonical_name(canonical_id)
            if not strategies:
                strategies = registry.get_by_canonical_name(strategy_id)
                
            for meta in strategies:
                if meta.version == version:
                    return meta.default_parameters
        
        # Fallback to latest or specific ID lookup
        meta = registry.get_or_none(strategy_id) or registry.get_or_none(canonical_id)
        if meta:
            return meta.default_parameters
            
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Error fetching default params for {strategy_id}: {e}")
        
    return {}
