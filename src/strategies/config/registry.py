"""Strategy Config Manager Registry - Maps strategy_id to Manager instances."""

from typing import Dict, Any, Type, Optional
from .manager_base import StrategyConfigManagerBase


class StrategyConfigManagerRegistry:
    """Registry to manage and look up strategy config managers."""
    
    _instance: Optional['StrategyConfigManagerRegistry'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StrategyConfigManagerRegistry, cls).__new__(cls)
            cls._instance._managers: Dict[str, StrategyConfigManagerBase] = {}
        return cls._instance
        
    def register(self, strategy_id: str, manager: StrategyConfigManagerBase) -> None:
        """Register a manager instance for a strategy_id."""
        self._managers[strategy_id] = manager
        
    def get_manager(self, strategy_id: str) -> Optional[StrategyConfigManagerBase]:
        """Get the manager for a given strategy_id."""
        return self._managers.get(strategy_id)
        
    def list_strategies(self) -> list:
        """List all registered strategy IDs."""
        return list(self._managers.keys())


# Global registry instance
config_manager_registry = StrategyConfigManagerRegistry()
