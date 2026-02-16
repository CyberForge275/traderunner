"""Strategy registry for managing and discovering trading strategies."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any, Dict, List, Optional, Type, Protocol


logger = logging.getLogger(__name__)


class IStrategy(Protocol):
    """Protocol for trading strategy implementations."""

    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    config_schema: Dict[str, Any] = {}

    def generate_signals(self, bars: Any) -> Any:
        ...

    def get_required_data_columns(self) -> List[str]:
        ...


class StrategyRegistry:
    """Registry for trading strategies with auto-discovery support.

    This registry maintains a mapping between strategy names and their
    implementation classes. It supports manual registration and
    automatic discovery of strategies in specific packages.
    """

    def __init__(self) -> None:
        """Initialize the strategy registry."""
        self._strategies: Dict[str, Type] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._discovery_paths: set[str] = set()

    def register(
        self, name: str, strategy_class: Type, metadata: Optional[Dict] = None
    ) -> None:
        """Register a strategy class with a name.

        Args:
            name: Unique name for the strategy
            strategy_class: Strategy implementation class
            metadata: Optional metadata (version, description, etc.)
        """
        if name in self._strategies:
            logger.warning("Overwriting strategy registration for: %s", name)

        self._strategies[name] = strategy_class
        self._metadata[name] = metadata or {}
        logger.debug("Registered strategy: %s (%s)", name, strategy_class.__name__)

    def get(self, name: str) -> Optional[Type]:
        """Get a strategy class by name.

        Args:
            name: Strategy name

        Returns:
            Strategy class if found, None otherwise
        """
        return self._strategies.get(name)

    def list_strategies(self) -> List[str]:
        """List all registered strategy names.

        Returns:
            List of strategy names
        """
        return sorted(list(self._strategies.keys()))

    def get_metadata(self, name: str) -> Optional[Dict]:
        """Get metadata for a registered strategy.

        Args:
            name: Strategy name

        Returns:
            Metadata dictionary if found, None otherwise
        """
        return self._metadata.get(name)

    def auto_discover(self, package_path: str = "strategies") -> int:
        """Automatically discover strategies in a package.

        Args:
            package_path: Package path to search (e.g., 'strategies')

        Returns:
            Number of newly discovered strategies
        """
        if package_path in self._discovery_paths:
            return 0

        self._discovery_paths.add(package_path)
        discovered = 0

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
                    except ImportError as exc:
                        logger.warning(
                            "Failed to import strategy package %s: %s",
                            modname,
                            exc,
                        )
                    except TypeError as exc:
                        logger.warning(
                            "Invalid strategy signature in %s: %s",
                            modname,
                            exc,
                        )
                    except ValueError as exc:
                        logger.warning(
                            "Strategy validation failed in %s: %s",
                            modname,
                            exc,
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

                    except (TypeError, ValueError) as exc:
                        logger.warning(
                            "Failed to register strategy %s from %s: %s",
                            attr_name,
                            strategy_module_name,
                            exc,
                        )

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

                        except (TypeError, ValueError) as exc:
                            logger.warning(
                                "Failed to register strategy %s from %s: %s",
                                attr_name,
                                alt_module_name,
                                exc,
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


# --- DECOUPLED PIPELINE PLUGIN SUPPORT ---

class StrategyPlugin(Protocol):
    strategy_id: str

    def get_schema(self, version: str):
        ...

    def extend_signal_frame(self, bars, params: dict):
        ...


_PLUGINS: Dict[str, StrategyPlugin] = {}

# Minimaler Lazy-Import, nur um InsideBar-Verhalten NICHT zu brechen
_AUTO_IMPORTS: Dict[str, str] = {
    "insidebar_intraday": "strategies.inside_bar",
    "confirmed_breakout_intraday": "strategies.confirmed_breakout",
}


def register_strategy(plugin: StrategyPlugin) -> None:
    _PLUGINS[plugin.strategy_id] = plugin


def get_strategy(strategy_id: str) -> StrategyPlugin:
    if strategy_id not in _PLUGINS and strategy_id in _AUTO_IMPORTS:
        importlib.import_module(_AUTO_IMPORTS[strategy_id])

    if strategy_id not in _PLUGINS:
        raise KeyError(
            f"Unknown strategy_id='{strategy_id}'. Registered={sorted(_PLUGINS.keys())}"
        )
    return _PLUGINS[strategy_id]


def _reset_for_tests() -> None:
    _PLUGINS.clear()
