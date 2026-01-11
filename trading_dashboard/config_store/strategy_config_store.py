"""Strategy Config Store - Bridge between Dashboard UI and SSOT Managers."""

import logging
from typing import Dict, Any, Optional
from src.strategies.config.managers.inside_bar_manager import InsideBarConfigManager

logger = logging.getLogger(__name__)


class StrategyConfigStore:
    """Provides validated strategy configuration defaults for the UI."""

    @staticmethod
    def get_defaults(strategy_id: str, version: str) -> Dict[str, Any]:
        """
        Get default parameters for a strategy version.
        
        SSOT-only: Loads exclusively from YAML via ManagerRegistry.
        No fallbacks. Raises on failure.
        
        Args:
            strategy_id: Unique strategy identifier (e.g. 'insidebar_intraday')
            version: Version string (e.g. '2.0.0')
            
        Returns:
            Dictionary with core, tunable, and metadata
            
        Raises:
            ValueError: If strategy_id is not registered or version not found
        """
        # Ensure managers are registered (manual discovery for now)
        from src.strategies.config.managers.inside_bar_manager import InsideBarConfigManager
        from src.strategies.config.registry import config_manager_registry
        
        # 1. Lookup manager
        manager = config_manager_registry.get_manager(strategy_id)
            
        if not manager:
            raise ValueError(
                f"No manager registered for strategy: {strategy_id}. "
                f"Available: {config_manager_registry.list_strategies()}"
            )
            
        # 2. Load version
        version_clean = version.lstrip('v') if version else "1.0.0"
        config = manager.get(version_clean)
        
        logger.info(f"actions: config_loaded strategy={strategy_id} version={version_clean} source=yaml")
        
        return {
            "strategy": strategy_id,
            "version": version_clean,
            "required_warmup_bars": config["required_warmup_bars"],
            "core": config["core"],
            "tunable": config.get("tunable", {}),
            "schema": {}
        }

    @staticmethod
    def save_new_version(
        strategy_id: str,
        base_version: str,
        new_version: str,
        core_overrides: Optional[Dict[str, Any]] = None,
        tunable_overrides: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save UI changes as new version (immutable).
        
        SSOT-only: Writes to YAML via Manager. No fallbacks.
        
        Args:
            strategy_id: Strategy identifier
            base_version: Version to copy from
            new_version: New version identifier
            core_overrides: Core parameter changes
            tunable_overrides: Tunable parameter changes
            
        Raises:
            ValueError: If strategy not registered, version exists, or validation fails
        """
        # Ensure managers are registered
        from src.strategies.config.managers.inside_bar_manager import InsideBarConfigManager
        from src.strategies.config.registry import config_manager_registry
        
        # Lookup manager
        manager = config_manager_registry.get_manager(strategy_id)
        
        if not manager:
            raise ValueError(
                f"No manager registered for strategy: {strategy_id}. "
                f"Available: {config_manager_registry.list_strategies()}"
            )
        
        # Delegate to manager
        manager.add_version(
            base_version=base_version,
            new_version=new_version,
            overrides_core=core_overrides,
            overrides_tunable=tunable_overrides
        )
        
        logger.info(
            f"actions: config_version_added strategy={strategy_id} "
            f"base={base_version} new={new_version}"
        )

    @staticmethod
    def update_existing_version(
        strategy_id: str,
        version: str,
        core_overrides: Optional[Dict[str, Any]] = None,
        tunable_overrides: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update existing version in-place (draft mode only).
        
        Args:
            strategy_id: Strategy identifier
            version: Version to update
            core_overrides: Core parameter changes
            tunable_overrides: Tunable parameter changes
            
        Raises:
            ValueError: If strategy not registered, version not found, or is finalized
        """
        from src.strategies.config.managers.inside_bar_manager import InsideBarConfigManager
        from src.strategies.config.registry import config_manager_registry
        
        manager = config_manager_registry.get_manager(strategy_id)
        
        if not manager:
            raise ValueError(
                f"No manager registered for strategy: {strategy_id}. "
                f"Available: {config_manager_registry.list_strategies()}"
            )
        
        manager.update_existing_version(
            version=version,
            overrides_core=core_overrides,
            overrides_tunable=tunable_overrides
        )
        
        logger.info(f"actions: config_version_updated strategy_id={strategy_id} version={version}")

    @staticmethod
    def mark_as_finalized(strategy_id: str, version: str) -> None:
        """Mark a version as fin alized (no further edits).
        
        Args:
            strategy_id: Strategy identifier
            version: Version to finalize
            
        Raises:
            ValueError: If strategy not registered or version not found
        """
        from src.strategies.config.managers.inside_bar_manager import InsideBarConfigManager
        from src.strategies.config.registry import config_manager_registry
        
        manager = config_manager_registry.get_manager(strategy_id)
        
        if not manager:
            raise ValueError(
                f"No manager registered for strategy: {strategy_id}. "
                f"Available: {config_manager_registry.list_strategies()}"
            )
        
        manager.mark_as_finalized(version)
        
        logger.info(f"actions: config_version_finalized strategy_id={strategy_id} version={version}")

    @staticmethod
    def get_field_specs(strategy_id: str) -> Dict[str, Any]:
        """Return field specifications for UI rendering."""
        from src.strategies.config.managers.inside_bar_manager import InsideBarConfigManager
        from src.strategies.config.registry import config_manager_registry
        
        manager = config_manager_registry.get_manager(strategy_id)
        if not manager:
            raise ValueError(f"No manager registered for strategy: {strategy_id}")
            
        return manager.get_field_specs()
