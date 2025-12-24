"""
Strategy Configuration Plugin System

Base classes and utilities for strategy-specific UI plugins.
"""
from typing import Dict, List, Callable, Any, Optional
from dash import html


class StrategyConfigPlugin:
    """Base class for strategy-specific UI configuration."""

    @property
    def strategy_id(self) -> str:
        """Unique strategy identifier (must match dropdown value)."""
        raise NotImplementedError("Subclasses must implement strategy_id")

    @property
    def display_name(self) -> str:
        """Human-readable strategy name."""
        return self.strategy_id

    def render_config_ui(self) -> List:
        """
        Render strategy-specific configuration UI elements.

        Returns:
            List of Dash components to display below strategy selector
        """
        return []

    def get_callbacks(self) -> List[Callable]:
        """
        Return list of callback registration functions.

        Each function should accept an app parameter and register callbacks.

        Returns:
            List of functions that register callbacks
        """
        return []

    def extract_config_from_inputs(self, **inputs) -> Dict[str, Any]:
        """
        Extract configuration dictionary from UI input values.

        Args:
            **inputs: Named input values from callback States

        Returns:
            Configuration dictionary to pass to backtest service
        """
        return {}


def create_empty_plugin() -> List:
    """Return empty UI for strategies without custom configuration."""
    return []
