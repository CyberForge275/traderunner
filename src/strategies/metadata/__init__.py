"""
Strategy Metadata Package
==========================

Enterprise-grade Single Source of Truth for all strategy metadata.

This package provides:
- StrategyMetadata schema with validation
- StrategyRegistry for centralized management
- Loaders for DB/YAML sources
- Validators for strategy definitions

Usage:
    from strategies.metadata import StrategyMetadata, StrategyRegistry
    
    # Get registry instance
    registry = StrategyRegistry()
    
    # Lookup strategy
    strategy = registry.get("inside_bar")
    
    # List all strategies
    all_strategies = registry.list_all()
"""

from .schema import (
    StrategyMetadata,
    StrategyCapabilities,
    DataRequirements,
    DeploymentInfo,
)
from .registry import StrategyRegistry

__all__ = [
    "StrategyMetadata",
    "StrategyCapabilities",
    "DataRequirements",
    "DeploymentInfo",
    "StrategyRegistry",
]

__version__ = "1.0.0"
