"""
Strategy Configuration Plugin Registry

Central registry for all strategy UI plugins.
"""
from typing import Dict, Optional, List
from dash import html

from . import StrategyConfigPlugin, create_empty_plugin
from .inside_bar_config import InsideBarConfigPlugin


class StrategyConfigRegistry:
    """Global registry for strategy configuration plugins."""
    
    def __init__(self):
        self.plugins: Dict[str, StrategyConfigPlugin] = {}
        self._register_builtin_plugins()
    
    def _register_builtin_plugins(self):
        """Register all built-in strategy plugins."""
        # Register InsideBar plugin
        insidebar_plugin = InsideBarConfigPlugin()
        self.register(insidebar_plugin)
        
        # Also register for v2 variant
        self.plugins["insidebar_intraday_v2"] = insidebar_plugin
        
        # Rudometkin will be added later
        # rudometkin_plugin = RudometkinConfigPlugin()
        # self.register(rudometkin_plugin)
    
    def register(self, plugin: StrategyConfigPlugin):
        """Register a strategy configuration plugin."""
        self.plugins[plugin.strategy_id] = plugin
    
    def get_plugin(self, strategy_id: str) -> Optional[StrategyConfigPlugin]:
        """Get plugin for given strategy ID."""
        return self.plugins.get(strategy_id)
    
    def has_custom_config(self, strategy_id: str) -> bool:
        """Check if strategy has custom configuration UI."""
        return strategy_id in self.plugins
    
    def render_config_for_strategy(self, strategy_id: str) -> List:
        """
        Render configuration UI for given strategy.
        
        Args:
            strategy_id: Strategy identifier
            
        Returns:
            List of Dash components or empty list
        """
        plugin = self.get_plugin(strategy_id)
        if plugin:
            return plugin.render_config_ui()
        return create_empty_plugin()
    
    def register_all_callbacks(self, app):
        """Register callbacks for all plugins."""
        for plugin in set(self.plugins.values()):  # Use set to avoid duplicates
            for callback_fn in plugin.get_callbacks():
                callback_fn(app)
    
    def extract_config(self, strategy_id: str, **inputs) -> Dict:
        """Extract configuration from inputs for given strategy."""
        plugin = self.get_plugin(strategy_id)
        if plugin:
            return plugin.extract_config_from_inputs(**inputs)
        return {}


# Global singleton instance
_registry = None


def get_registry() -> StrategyConfigRegistry:
    """Get global registry instance (singleton pattern)."""
    global _registry
    if _registry is None:
        _registry = StrategyConfigRegistry()
    return _registry


def initialize_registry(app):
    """Initialize registry and register all callbacks."""
    registry = get_registry()
    registry.register_all_callbacks(app)
    return registry
