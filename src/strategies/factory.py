#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 14 17:19:28 2025

@author: mirko
"""

"""Strategy factory for creating and configuring trading strategy instances."""

import logging
from typing import Dict, Any, Optional, List

from .base import IStrategy
from .registry import registry

logger = logging.getLogger(__name__)


class StrategyFactory:
    """Factory for creating strategy instances with configuration validation.

    This factory provides:
    - Strategy instance creation with validation
    - Configuration schema validation
    - Error handling and logging
    - Strategy lifecycle management
    """

    @staticmethod
    def create_strategy(
        name: str, config: Dict[str, Any], validate_config: bool = True
    ) -> IStrategy:
        """Create a strategy instance from name and configuration.

        Args:
            name: Strategy name (must be registered in registry)
            config: Strategy configuration parameters
            validate_config: Whether to validate configuration against schema

        Returns:
            Configured strategy instance

        Raises:
            ValueError: If strategy not found or configuration invalid
            RuntimeError: If strategy instantiation fails
        """
        logger.debug(f"Creating strategy: {name} with config: {config}")

        # Get strategy class from registry
        strategy_class = registry.get(name)
        if not strategy_class:
            available = registry.list_strategies()
            raise ValueError(
                f"Unknown strategy: '{name}'. "
                f"Available strategies: {available}. "
                f"Make sure to call registry.auto_discover() first."
            )

        try:
            # Create strategy instance
            strategy_instance = strategy_class()

            # Validate configuration if requested
            if validate_config and not strategy_instance.validate_config(config):
                schema = strategy_instance.config_schema
                raise ValueError(
                    f"Invalid configuration for strategy '{name}'. "
                    f"Expected schema: {schema}"
                )

            # Apply configuration if the strategy supports it
            if hasattr(strategy_instance, "_config") and hasattr(
                strategy_instance._config, "name"
            ):
                strategy_instance._config.name = name

            if hasattr(strategy_instance, "configure"):
                strategy_instance.configure(config)
            elif hasattr(strategy_instance, "_config"):
                if hasattr(strategy_instance._config, "parameters"):
                    strategy_instance._config.parameters.update(config)

            logger.info(f"Created strategy instance: {name}")
            return strategy_instance

        except ValueError:
            raise
        except TypeError as exc:
            logger.error(
                "Failed to instantiate strategy '%s': %s",
                name,
                exc,
                exc_info=True,
            )
            raise RuntimeError(f"Strategy instantiation failed: {exc}") from exc
        except Exception as exc:
            logger.exception("Unexpected error creating strategy '%s'", name)
            raise RuntimeError(f"Strategy instantiation failed: {exc}") from exc

    @staticmethod
    def create_strategy_with_defaults(
        name: str, config: Optional[Dict[str, Any]] = None
    ) -> IStrategy:
        """Create a strategy instance with default configuration.

        Args:
            name: Strategy name
            config: Optional configuration overrides

        Returns:
            Strategy instance with default configuration
        """
        config = config or {}

        # Get default configuration from strategy
        strategy_class = registry.get(name)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: '{name}'")

        try:
            # Create temporary instance to get defaults
            temp_instance = strategy_class()
            schema = temp_instance.config_schema

            # Extract default values from schema
            default_config = {}
            properties = schema.get("properties", {})
            for field_name, field_info in properties.items():
                if "default" in field_info:
                    default_config[field_name] = field_info["default"]

            # Merge with provided config
            final_config = {**default_config, **config}

            return StrategyFactory.create_strategy(name, final_config)

        except (TypeError, ValueError) as exc:
            logger.error(
                "Failed to create strategy with defaults '%s': %s",
                name,
                exc,
            )
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error building defaults for strategy '%s'", name
            )
            raise

    @staticmethod
    def create_multiple_strategies(
        strategy_configs: List[Dict[str, Any]],
    ) -> Dict[str, IStrategy]:
        """Create multiple strategy instances from configuration list.

        Args:
            strategy_configs: List of strategy configurations.
                Each config should have 'name' and 'config' keys.

        Returns:
            Dictionary mapping strategy names to instances

        Raises:
            ValueError: If any strategy creation fails
        """
        strategies = {}
        failed = []

        for i, strategy_config in enumerate(strategy_configs):
            try:
                name = strategy_config.get("name")
                config = strategy_config.get("config", {})

                if not name:
                    raise ValueError(f"Strategy config {i} missing 'name' field")

                # Create unique instance name if duplicates
                instance_name = name
                counter = 1
                while instance_name in strategies:
                    instance_name = f"{name}_{counter}"
                    counter += 1

                strategy = StrategyFactory.create_strategy(name, config)
                strategies[instance_name] = strategy

                logger.info(f"Created strategy instance: {instance_name}")

            except (TypeError, ValueError) as exc:
                error_msg = f"Failed to create strategy {i}: {exc}"
                failed.append(error_msg)
                logger.error(error_msg)
            except Exception as exc:
                error_msg = f"Unexpected error creating strategy {i}: {exc}"
                failed.append(error_msg)
                logger.exception(error_msg)

        if failed:
            raise ValueError(f"Failed to create {len(failed)} strategies: {failed}")

        return strategies

    @staticmethod
    def list_available_strategies() -> List[str]:
        """Get list of available strategies for creation.

        Returns:
            List of strategy names available for creation
        """
        return registry.list_strategies()

    @staticmethod
    def get_strategy_schema(name: str) -> Dict[str, Any]:
        """Get configuration schema for a strategy.

        Args:
            name: Strategy name

        Returns:
            Strategy configuration schema

        Raises:
            ValueError: If strategy not found
        """
        strategy_class = registry.get(name)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: '{name}'")

        try:
            instance = strategy_class()
            return instance.config_schema
        except (TypeError, ValueError) as exc:
            logger.error(
                "Failed to get schema for strategy '%s': %s",
                name,
                exc,
            )
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error while retrieving schema for '%s'", name
            )
            raise

    @staticmethod
    def validate_strategy_config(name: str, config: Dict[str, Any]) -> bool:
        """Validate configuration for a strategy without creating instance.

        Args:
            name: Strategy name
            config: Configuration to validate

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If strategy not found
        """
        strategy_class = registry.get(name)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: '{name}'")

        try:
            instance = strategy_class()
            return instance.validate_config(config)
        except (TypeError, ValueError) as exc:
            logger.error(
                "Failed to validate config for strategy '%s': %s",
                name,
                exc,
            )
            return False
        except Exception as exc:
            logger.exception(
                "Unexpected error while validating config for '%s'", name
            )
            return False

    @staticmethod
    def get_strategy_info(name: str) -> Dict[str, Any]:
        """Get comprehensive information about a strategy.

        Args:
            name: Strategy name

        Returns:
            Dictionary with strategy information

        Raises:
            ValueError: If strategy not found
        """
        strategy_class = registry.get(name)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: '{name}'")

        try:
            instance = strategy_class()
            metadata = registry.get_metadata(name) or {}

            return {
                "name": name,
                "class": strategy_class.__name__,
                "version": getattr(instance, "version", "unknown"),
                "description": getattr(instance, "description", ""),
                "config_schema": instance.config_schema,
                "required_columns": instance.get_required_data_columns(),
                "metadata": metadata,
            }

        except (TypeError, ValueError) as exc:
            logger.error(
                "Failed to get info for strategy '%s': %s",
                name,
                exc,
            )
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error retrieving info for strategy '%s'", name
            )
            raise

    @staticmethod
    def create_strategy_from_config_file(
        config_file_path: str, config_format: str = "auto"
    ) -> IStrategy:
        """Create strategy from configuration file.

        Args:
            config_file_path: Path to configuration file
            config_format: Configuration format ('json', 'yaml', 'auto')

        Returns:
            Configured strategy instance

        Raises:
            ValueError: If file not found or invalid format
            RuntimeError: If strategy creation fails
        """
        import json
        from pathlib import Path

        config_path = Path(config_file_path)
        if not config_path.exists():
            raise ValueError(f"Configuration file not found: {config_file_path}")

        # Determine format
        if config_format == "auto":
            suffix = config_path.suffix.lower()
            if suffix in [".json"]:
                config_format = "json"
            elif suffix in [".yaml", ".yml"]:
                config_format = "yaml"
            else:
                raise ValueError(
                    f"Cannot auto-detect format for file: {config_file_path}"
                )

        # Load configuration
        try:
            if config_format == "json":
                with open(config_path) as f:
                    config_data = json.load(f)
            elif config_format == "yaml":
                try:
                    import yaml

                    with open(config_path) as f:
                        config_data = yaml.safe_load(f)
                except ImportError:
                    raise ValueError(
                        "PyYAML not installed, cannot load YAML configuration"
                    )
            else:
                raise ValueError(f"Unsupported configuration format: {config_format}")

            # Extract strategy name and config
            strategy_name = config_data.get("strategy")
            strategy_config = config_data.get("config", {})

            if not strategy_name:
                raise ValueError("Configuration file missing 'strategy' field")

            return StrategyFactory.create_strategy(strategy_name, strategy_config)

        except (TypeError, ValueError) as exc:
            logger.error(
                "Failed to create strategy from config file '%s': %s",
                config_file_path,
                exc,
            )
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error creating strategy from '%s'",
                config_file_path,
            )
            raise


# Convenience functions for common use cases
def create_strategy(name: str, config: Dict[str, Any] = None) -> IStrategy:
    """Convenience function to create a strategy.

    Args:
        name: Strategy name
        config: Strategy configuration

    Returns:
        Strategy instance
    """
    return StrategyFactory.create_strategy(name, config or {})


def list_strategies() -> List[str]:
    """Convenience function to list available strategies.

    Returns:
        List of strategy names
    """
    return StrategyFactory.list_available_strategies()


def get_strategy_schema(name: str) -> Dict[str, Any]:
    """Convenience function to get strategy schema.

    Args:
        name: Strategy name

    Returns:
        Strategy configuration schema
    """
    return StrategyFactory.get_strategy_schema(name)
