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
    strategy = registry.get("inside_bar_v2")
    
    # List all strategies
    all_strategies = registry.list_all()
"""

from .schema import (
    StrategyMetadata,
    StrategyCapabilities,
    DataRequirements,
    DeploymentInfo,
)

__all__ = [
    "StrategyMetadata",
    "StrategyCapabilities",
    "DataRequirements",
    "DeploymentInfo",
]

__version__ = "1.0.0"
