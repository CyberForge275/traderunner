"""
Strategy Registry Utilities

This module provides utilities to dynamically load strategy names from the 
source of truth (STRATEGY_REGISTRY in state.py) to prevent hardcoding mismatches.

Usage in dashboard layouts:
    from trading_dashboard.utils.strategy_helpers import get_strategy_options
    
    dcc.Dropdown(
        id="backtests-new-strategy",
        options=get_strategy_options(),
        value=get_default_strategy(),
        ...
    )
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

# Ensure apps directory is in path
ROOT = Path(__file__).resolve().parents[2]
APPS_DIR = ROOT / "apps"
if str(APPS_DIR) not in sys.path:
    sys.path.insert(0, str(APPS_DIR))


def get_strategy_registry() -> Dict:
    """
    Get the STRATEGY_REGISTRY from apps/streamlit/state.py.
    
    This is the single source of truth for available strategies.
    
    Returns:
        Dictionary mapping strategy keys to StrategyMetadata objects
    """
    try:
        from apps.streamlit.state import STRATEGY_REGISTRY
        return STRATEGY_REGISTRY
    except ImportError as e:
        print(f"Warning: Could not import STRATEGY_REGISTRY: {e}")
        return {}


def get_strategy_options() -> List[Dict[str, str]]:
    """
    Get dropdown options for strategy selection.
    
    Dynamically loads from STRATEGY_REGISTRY to ensure consistency.
    
    Returns:
        List of dicts with 'label' and 'value' keys for Dash dropdown
    """
    registry = get_strategy_registry()
    
    # Map strategy keys to human-readable labels
    label_map = {
        "insidebar_intraday": "Inside Bar",
        "insidebar_intraday_v2": "Inside Bar V2",
        "rudometkin_moc_mode": "Rudometkin",
    }
    
    options = []
    for key, metadata in registry.items():
        label = label_map.get(key, metadata.label if hasattr(metadata, 'label') else key)
        options.append({"label": label, "value": key})
    
    # Sort by label for consistent ordering
    options.sort(key=lambda x: x["label"])
    
    return options


def get_default_strategy() -> Optional[str]:
    """
    Get the default strategy key.
    
    Returns:
        Default strategy key (first alphabetically) or None if no strategies
    """
    options = get_strategy_options()
    if not options:
        return None
    
    # Return "Inside Bar" as default if available, otherwise first option
    for opt in options:
        if opt["label"] == "Inside Bar":
            return opt["value"]
    
    return options[0]["value"]


def validate_strategy_name(strategy_name: str) -> bool:
    """
    Validate that a strategy name exists in the registry.
    
    Args:
        strategy_name: Strategy key to validate
        
    Returns:
        True if valid, False otherwise
    """
    registry = get_strategy_registry()
    return strategy_name in registry


def get_available_strategies() -> List[str]:
    """
    Get list of all available strategy keys.
    
    Returns:
        List of strategy keys
    """
    registry = get_strategy_registry()
    return list(registry.keys())
