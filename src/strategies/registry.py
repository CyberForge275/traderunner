#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 14 17:20:01 2025

@author: mirko
"""

"""Strategy registry for managing and discovering trading strategies."""

import importlib
import pkgutil
import logging
from typing import Dict, Type, List, Optional, Set

from .base import IStrategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """Central registry for all trading strategies.

    This registry provides:
    - Strategy registration and lookup
    - Auto-discovery of strategy modules
    - Strategy validation and metadata management
    - Thread-safe operations for concurrent access
    """

    def __init__(self):
        """Initialize the strategy registry."""
        self._strategies: Dict[str, Type[IStrategy]] = {}
        self._metadata: Dict[str, Dict] = {}
        self._discovery_paths: Set[str] = set()

    def register(
        self,
        name: str,
        strategy_class: Type[IStrategy],
        metadata: Optional[Dict] = None,
    ) -> None:
        """Register a strategy class.

        Args:
            name: Unique strategy name
            strategy_class: Strategy class implementing IStrategy
            metadata: Optional metadata about the strategy

        Raises:
            ValueError: If strategy name already exists or class is invalid
        """
        if not name:
            raise ValueError("Strategy name cannot be empty")

        if name in self._strategies:
            raise ValueError(f"Strategy '{name}' is already registered")

        # Validate strategy class implements IStrategy protocol
        if not self._validate_strategy_class(strategy_class):
            raise ValueError(
                f"Strategy class {strategy_class} does not implement IStrategy protocol"
            )

        self._strategies[name] = strategy_class
        self._metadata[name] = metadata or {}

        logger.info(f"Registered strategy: {name}")

    def unregister(self, name: str) -> bool:
        """Unregister a strategy.

        Args:
            name: Strategy name to unregister

        Returns:
            True if strategy was unregistered, False if not found
        """
        if name in self._strategies:
            del self._strategies[name]
            self._metadata.pop(name, None)
            logger.info(f"Unregistered strategy: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[Type[IStrategy]]:
        """Get strategy class by name.

        Args:
            name: Strategy name

        Returns:
            Strategy class or None if not found
        """
        return self._strategies.get(name)

    def list_strategies(self) -> List[str]:
        """Get list of all registered strategy names.

        Returns:
            List of strategy names
        """
        return list(self._strategies.keys())

    def get_metadata(self, name: str) -> Optional[Dict]:
        """Get metadata for a strategy.

        Args:
            name: Strategy name

        Returns:
            Strategy metadata dictionary or None if not found
        """
        return self._metadata.get(name)

    def clear(self) -> None:
        """Clear all registered strategies."""
        count = len(self._strategies)
        self._strategies.clear()
        self._metadata.clear()
        logger.info(f"Cleared {count} strategies from registry")

    def auto_discover(self, package_path: str = "strategies") -> int:
        """Auto-discover strategies in a package.

        Args:
            package_path: Package path to search for strategies

        Returns:
            Number of strategies discovered and registered
        """
        discovered = 0
        self._discovery_paths.add(package_path)

        try:
            # Import the base package
            base_package = importlib.import_module(package_path)

            # Search for strategy modules
            for importer, modname, ispkg in pkgutil.iter_modules(
                base_package.__path__, base_package.__name__ + "."
            ):
                if ispkg:  # Strategy packages (e.g., strategies.inside_bar)
                    try:
                        discovered += self._discover_strategy_package(modname)
                    except Exception as e:
                        logger.warning(
                            f"Failed to discover strategies in {modname}: {e}"
                        )

        except ImportError as e:
            logger.error(f"Failed to import package {package_path}: {e}")

        logger.info(f"Auto-discovery found {discovered} strategies in {package_path}")
        return discovered

    def _discover_strategy_package(self, package_name: str) -> int:
        """Discover strategies in a specific package.

        Args:
            package_name: Full package name (e.g., 'strategies.inside_bar')

        Returns:
            Number of strategies found in this package
        """
        discovered = 0

        try:
            # Try to import the strategy module within the package
            strategy_module_name = f"{package_name}.strategy"
            strategy_module = importlib.import_module(strategy_module_name)

            # Look for strategy classes in the module
            for attr_name in dir(strategy_module):
                attr = getattr(strategy_module, attr_name)

                # Check if it's a strategy class
                if (
                    isinstance(attr, type)
                    and hasattr(attr, "name")
                    and hasattr(attr, "generate_signals")
                    and attr_name != "BaseStrategy"
                ):  # Skip base classes

                    try:
                        # Create instance to get name
                        instance = attr()
                        strategy_name = instance.name

                        # Register if not already registered
                        if strategy_name not in self._strategies:
                            metadata = {
                                "module": strategy_module_name,
                                "class_name": attr_name,
                                "package": package_name,
                                "version": getattr(instance, "version", "1.0.0"),
                                "description": getattr(instance, "description", ""),
                            }

                            self.register(strategy_name, attr, metadata)
                            discovered += 1

                    except Exception as e:
                        logger.warning(f"Failed to register strategy {attr_name}: {e}")

        except ImportError:
            # Try alternative naming (e.g., strategies.inside_bar.inside_bar)
            try:
                # Extract strategy name from package
                # (e.g., 'inside_bar' from 'strategies.inside_bar')
                strategy_name = package_name.split(".")[-1]
                alt_module_name = f"{package_name}.{strategy_name}"
                alt_module = importlib.import_module(alt_module_name)

                # Look for strategy classes
                for attr_name in dir(alt_module):
                    attr = getattr(alt_module, attr_name)

                    if (
                        isinstance(attr, type)
                        and hasattr(attr, "name")
                        and hasattr(attr, "generate_signals")
                    ):

                        try:
                            instance = attr()
                            if instance.name not in self._strategies:
                                metadata = {
                                    "module": alt_module_name,
                                    "class_name": attr_name,
                                    "package": package_name,
                                }

                                self.register(instance.name, attr, metadata)
                                discovered += 1

                        except Exception as e:
                            logger.warning(
                                f"Failed to register strategy {attr_name}: {e}"
                            )

            except ImportError:
                # No strategies found in this package
                pass

        return discovered

    def _validate_strategy_class(self, strategy_class: Type) -> bool:
        """Validate that a class implements the IStrategy protocol.

        Args:
            strategy_class: Class to validate

        Returns:
            True if class implements IStrategy protocol
        """
        try:
            # Check if class has required methods
            required_methods = ["name", "generate_signals", "get_required_data_columns"]
            required_properties = ["config_schema"]

            for method in required_methods:
                if not hasattr(strategy_class, method):
                    logger.warning(
                        f"Strategy class {strategy_class} missing method: {method}"
                    )
                    return False

            for prop in required_properties:
                if not hasattr(strategy_class, prop):
                    logger.warning(
                        f"Strategy class {strategy_class} missing property: {prop}"
                    )
                    return False

            # Try to instantiate to check basic functionality
            instance = strategy_class()
            if not isinstance(instance.name, str) or not instance.name:
                logger.warning(
                    f"Strategy class {strategy_class} has invalid name property"
                )
                return False

            return True

        except Exception as e:
            logger.warning(
                f"Validation failed for strategy class {strategy_class}: {e}"
            )
            return False

    def get_strategies_by_type(self, strategy_type: str) -> List[str]:
        """Get strategies filtered by type from metadata.

        Args:
            strategy_type: Type to filter by (e.g., 'technical', 'fundamental')

        Returns:
            List of strategy names matching the type
        """
        matching = []
        for name, metadata in self._metadata.items():
            if metadata.get("type") == strategy_type:
                matching.append(name)
        return matching

    def get_discovery_stats(self) -> Dict:
        """Get statistics about strategy discovery.

        Returns:
            Dictionary with discovery statistics
        """
        return {
            "total_strategies": len(self._strategies),
            "discovery_paths": list(self._discovery_paths),
            "strategies": {
                name: {
                    "class": cls.__name__,
                    "module": self._metadata.get(name, {}).get(
                        "module", "unknown"
                    ),
                }
                for name, cls in self._strategies.items()
            },
        }


# Global registry instance
registry = StrategyRegistry()
