"""
StrategyRegistry - Singleton for Strategy Management
====================================================

Thread-safe singleton registry for all strategy metadata.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Callable
from pathlib import Path
import json

from .schema import StrategyMetadata, StrategyCapabilities, DeploymentEnvironment


class StrategyRegistry:
    """
    Thread-safe singleton registry for strategy metadata.
    
    This is the ONLY place to register and lookup strategies.
    All systems must use this registry.
    
    Usage:
        registry = StrategyRegistry()
        registry.register(metadata)
        strategy = registry.get("inside_bar_v2")
    """
    
    _instance: Optional[StrategyRegistry] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> StrategyRegistry:
        """Singleton pattern - only one instance ever exists."""
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize registry (only once)."""
        if self._initialized:
            return
        
        self._strategies: Dict[str, StrategyMetadata] = {}
        self._lock_registry = threading.RLock()  # Re-entrant lock for thread safety
        self._initialized = True
    
    def register(self, metadata: StrategyMetadata) -> None:
        """
        Register a strategy in the registry.
        
        Args:
            metadata: StrategyMetadata instance
            
        Raises:
            ValueError: If strategy_id already registered
            ValueError: If metadata validation fails
        """
        # Validate metadata
        metadata.validate()
        
        with self._lock_registry:
            if metadata.strategy_id in self._strategies:
                raise ValueError(
                    f"Strategy '{metadata.strategy_id}' already registered. "
                    f"Use update() to modify existing strategy."
                )
            
            self._strategies[metadata.strategy_id] = metadata
    
    def update(self, metadata: StrategyMetadata) -> None:
        """
        Update existing strategy metadata.
        
        Args:
            metadata: Updated StrategyMetadata
            
        Raises:
            ValueError: If strategy_id not found
        """
        metadata.validate()
        
        with self._lock_registry:
            if metadata.strategy_id not in self._strategies:
                raise ValueError(
                    f"Strategy '{metadata.strategy_id}' not found. "
                    f"Use register() to add new strategy."
                )
            
            self._strategies[metadata.strategy_id] = metadata
    
    def get(self, strategy_id: str) -> StrategyMetadata:
        """
        Get strategy metadata by ID.
        
        Args:
            strategy_id: Unique strategy identifier
            
        Returns:
            StrategyMetadata instance
            
        Raises:
            KeyError: If strategy not found
        """
        with self._lock_registry:
            if strategy_id not in self._strategies:
                available = list(self._strategies.keys())
                raise KeyError(
                    f"Strategy '{strategy_id}' not found. "
                    f"Available: {available}"
                )
            
            return self._strategies[strategy_id]
    
    def get_or_none(self, strategy_id: str) -> Optional[StrategyMetadata]:
        """
        Get strategy metadata, return None if not found.
        
        Args:
            strategy_id: Unique strategy identifier
            
        Returns:
            StrategyMetadata or None
        """
        with self._lock_registry:
            return self._strategies.get(strategy_id)
    
    def list_all(self) -> List[StrategyMetadata]:
        """
        List all registered strategies.
        
        Returns:
            List of StrategyMetadata instances
        """
        with self._lock_registry:
            return list(self._strategies.values())
    
    def list_ids(self) -> List[str]:
        """
        List all strategy IDs.
        
        Returns:
            List of strategy_id strings
        """
        with self._lock_registry:
            return list(self._strategies.keys())
    
    def get_by_canonical_name(self, canonical_name: str) -> List[StrategyMetadata]:
        """
        Get all strategies with given canonical name (all versions).
        
        Args:
            canonical_name: Base strategy name (e.g., "inside_bar")
            
        Returns:
            List of matching StrategyMetadata instances
        """
        with self._lock_registry:
            return [
                meta for meta in self._strategies.values()
                if meta.canonical_name == canonical_name
            ]
    
    def get_by_capability(
        self,
        capability_filter: Callable[[StrategyCapabilities], bool]
    ) -> List[StrategyMetadata]:
        """
        Get strategies matching capability filter.
        
        Args:
            capability_filter: Function that takes Capabilities and returns bool
            
        Returns:
            List of matching strategies
            
        Example:
            # Get all live-trading-capable strategies
            live_strategies = registry.get_by_capability(
                lambda cap: cap.supports_live_trading
            )
        """
        with self._lock_registry:
            return [
                meta for meta in self._strategies.values()
                if capability_filter(meta.capabilities)
            ]
    
    def get_for_environment(
        self,
        environment: DeploymentEnvironment
    ) -> List[StrategyMetadata]:
        """
        Get strategies compatible with deployment environment.
        
        Args:
            environment: Target deployment environment
            
        Returns:
            List of compatible strategies
        """
        with self._lock_registry:
            return [
                meta for meta in self._strategies.values()
                if meta.is_compatible_with_environment(environment)
            ]
    
    def exists(self, strategy_id: str) -> bool:
        """
        Check if strategy exists in registry.
        
        Args:
            strategy_id: Strategy ID to check
            
        Returns:
            True if exists, False otherwise
        """
        with self._lock_registry:
            return strategy_id in self._strategies
    
    def unregister(self, strategy_id: str) -> None:
        """
        Remove strategy from registry.
        
        Args:
            strategy_id: Strategy to remove
            
        Raises:
            KeyError: If strategy not found
        """
        with self._lock_registry:
            if strategy_id not in self._strategies:
                raise KeyError(f"Strategy '{strategy_id}' not found")
            
            del self._strategies[strategy_id]
    
    def clear(self) -> None:
        """
        Clear all strategies from registry.
        
        WARNING: This is mainly for testing. Use with caution.
        """
        with self._lock_registry:
            self._strategies.clear()
    
    def count(self) -> int:
        """
        Get number of registered strategies.
        
        Returns:
            Count of strategies
        """
        with self._lock_registry:
            return len(self._strategies)
    
    def to_json(self, filepath: Path) -> None:
        """
        Export registry to JSON file.
        
        Args:
            filepath: Path to JSON file
        """
        with self._lock_registry:
            data = {
                strategy_id: meta.to_dict()
                for strategy_id, meta in self._strategies.items()
            }
        
        filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    
    def from_json(self, filepath: Path) -> None:
        """
        Import strategies from JSON file.
        
        Args:
            filepath: Path to JSON file
            
        Note: This ADDS to existing strategies, does not replace
        """
        data = json.loads(filepath.read_text(encoding="utf-8"))
        
        for strategy_id, meta_dict in data.items():
            metadata = StrategyMetadata.from_dict(meta_dict)
            
            # Use update if exists, register if new
            if self.exists(strategy_id):
                self.update(metadata)
            else:
                self.register(metadata)
    
    def __repr__(self) -> str:
        """String representation."""
        with self._lock_registry:
            count = len(self._strategies)
            ids = list(self._strategies.keys())[:3]
            truncated = "..." if count > 3 else ""
            return f"StrategyRegistry({count} strategies: {ids}{truncated})"
    
    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset singleton instance.
        
        WARNING: Only for testing! This breaks singleton pattern.
        """
        with cls._lock:
            cls._instance = None
