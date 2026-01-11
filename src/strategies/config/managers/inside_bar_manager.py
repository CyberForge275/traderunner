"""InsideBar Config Manager - Handles loading and validation of InsideBar configurations."""

from typing import Dict, Any
from ..manager_base import StrategyConfigManagerBase
from ..specs.inside_bar_spec import InsideBarSpec


class InsideBarConfigManager(StrategyConfigManagerBase):
    """Config manager for InsideBar strategy."""
    
    strategy_id = "insidebar_intraday"
    
    def __init__(self, repository=None):
        """Initialize with repository and spec."""
        super().__init__(repository=repository)
        self.spec = InsideBarSpec()



    def get(self, version: str) -> Dict[str, Any]:
        """
        Get and validate a specific version of InsideBar config.
        
        Args:
            version: Version string (e.g. '1.0.0')
            
        Returns:
            Validated configuration node
        """
        return self.get_version(version)

    def validate(self, version: str, node: Dict[str, Any]) -> None:
        """
        Perform strict validation of InsideBar config node.
        
        Args:
            version: Version string
            node: Configuration node to validate
        """
        # 1. Base validation (warmup_bars, core existence, etc.)
        super().validate(version, node)
        
        # 2. Spec-specific validation for core
        self.spec.validate_core(version, node["core"])
        
        # 3. Spec-specific validation for tunable (if exists)
        if "tunable" in node:
            self.spec.validate_tunable(version, node["tunable"])

    def get_metadata(self) -> Dict[str, Any]:
        """Get strategy metadata from YAML."""
        config = self.load()
        self.spec.validate_top_level(config)
        
        return {
            "strategy_id": config.get("strategy_id"),
            "canonical_name": config.get("canonical_name"),
            "versions": list(config.get("versions", {}).keys())
        }

    def get_field_specs(self) -> Dict[str, Any]:
        """Return field specifications for UI rendering."""
        return self.spec.get_field_specs()

# Register in global registry
from ..registry import config_manager_registry
config_manager_registry.register(InsideBarConfigManager.strategy_id, InsideBarConfigManager())
