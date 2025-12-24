"""
Visualization layer for trading dashboard.
Provides chart builders that convert domain data to visual representations.

This layer is framework-agnostic and can be used with different UI frameworks
(Dash, Streamlit, etc.) or chart libraries (Plotly, Bokeh, lightweight-charts).
"""
from typing import Protocol, Any

__version__ = "1.0.0"
__all__ = ["ChartBuilder"]


class ChartBuilder(Protocol):
    """
    Protocol for chart builder implementations.
    
    Chart builders take domain data (DataFrames, configs) and produce
    framework-specific chart objects.
    """
    
    def build(self, *args: Any, **kwargs: Any) -> Any:
        """
        Build and return a chart figure.
        
        Returns:
            Framework-specific chart object (e.g., go.Figure for Plotly)
        """
        ...
