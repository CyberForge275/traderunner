"""Base Strategy Config Manager - Provides unified load/validate interface."""

import copy
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
from .repository import StrategyConfigRepository


class StrategyConfigManagerBase:
    """Base class for strategy configuration managers."""
    
    strategy_id: str = ""
    
    def __init__(self, repository: Optional[StrategyConfigRepository] = None):
        """
        Initialize manager with repository.
        
        Args:
            repository: StrategyConfigRepository instance
        """
        self.repository = repository or StrategyConfigRepository()

    def load(self) -> Dict[str, Any]:
        """Load the entire strategy config file."""
        if not self.strategy_id:
            raise ValueError("strategy_id must be defined in subclass")
        return self.repository.read_strategy_file(self.strategy_id)

    def get_version(self, version: str) -> Dict[str, Any]:
        """
        Get and validate a specific version of the strategy config.
        
        Args:
            version: Version string (e.g. '1.0.0')
            
        Returns:
            Validated configuration node
            
        Raises:
            ValueError: If version not found or validation fails
        """
        config = self.load()
        
        # 1. Validate top-level strategy_id match
        yaml_strategy_id = config.get("strategy_id")
        if yaml_strategy_id != self.strategy_id:
            raise ValueError(
                f"Strategy ID mismatch: expected '{self.strategy_id}', "
                f"found '{yaml_strategy_id}' in YAML"
            )
            
        versions = config.get("versions", {})
        version_node = versions.get(version)
        if not version_node:
            raise ValueError(f"Version '{version}' not found for strategy '{self.strategy_id}'")
            
        self.validate(version, version_node)
        return version_node

    def add_version(
        self,
        base_version: str,
        new_version: str,
        overrides_core: Optional[Dict[str, Any]] = None,
        overrides_tunable: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add new version based on existing version + overrides (immutable).
        
        Args:
            base_version: Existing version to copy from
            new_version: New version identifier
            overrides_core: Core parameter overrides
            overrides_tunable: Tunable parameter overrides
            
        Raises:
            ValueError: If new_version already exists or validation fails
        """
        # 1. Load full YAML
        config = self.load()
        versions = config.get("versions", {})
        
        # 2. Check new_version doesn't exist
        if new_version in versions:
            raise ValueError(
                f"Version '{new_version}' already exists for strategy '{self.strategy_id}'"
            )
        
        # 3. Check base_version exists
        if base_version not in versions:
            raise ValueError(
                f"Base version '{base_version}' not found for strategy '{self.strategy_id}'"
            )
        
        # 4. Deep copy base version node
        new_node = copy.deepcopy(versions[base_version])
        
        # 5. Apply overrides
        if overrides_core:
            new_node.setdefault("core", {}).update(overrides_core)
        if overrides_tunable:
            new_node.setdefault("tunable", {}).update(overrides_tunable)
        
        # 6. Validate new node
        self.validate(new_version, new_node)
        
        # 7. Add to versions
        versions[new_version] = new_node
        
        # 8. Write back atomically
        self.repository.write_strategy_file(self.strategy_id, config)

    def validate(self, version: str, node: Dict[str, Any]) -> None:
        """
        Validate a configuration node. Must be implemented by subclass.
        
        Args:
            version: Version string
            node: Configuration node to validate
            
        Raises:
            ValueError: If validation fails
        """
        # Base class only checks basic structure common to all strategies
        self._validate_common(version, node)

    def _validate_common(self, version: str, node: Dict[str, Any]) -> None:
        """Validate common attributes present in all strategy configs."""
        # 1. required_warmup_bars
        if "required_warmup_bars" not in node:
            raise ValueError(f"{self.strategy_id} v{version} missing: required_warmup_bars")
            
        warmup = node["required_warmup_bars"]
        if not isinstance(warmup, int) or warmup < 0:
            raise ValueError(
                f"{self.strategy_id} v{version} invalid required_warmup_bars: "
                f"{warmup} (must be int >= 0)"
            )
            
        # 2. core block must exist
        if "core" not in node:
            raise ValueError(f"{self.strategy_id} v{version} missing: core")
            
        if not isinstance(node["core"], dict):
            raise ValueError(f"{self.strategy_id} v{version} core must be a dictionary")
            
        # 3. tunable block (optional)
        if "tunable" in node and not isinstance(node["tunable"], dict):
            raise ValueError(f"{self.strategy_id} v{version} tunable must be a dictionary")
            
        # 4. Strictness: No unknown top-level keys in version node
        allowed_keys = {"required_warmup_bars", "core", "tunable", "strategy_finalized"}
        unknown_keys = set(node.keys()) - allowed_keys
        if unknown_keys:
            raise ValueError(
                f"{self.strategy_id} v{version} unknown keys: {', '.join(unknown_keys)}"
            )

    def update_existing_version(
        self,
        version: str,
        overrides_core: Optional[Dict[str, Any]] = None,
        overrides_tunable: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update existing version in-place (only allowed if strategy_finalized=false).
        
        Args:
            version: Version to update
            overrides_core: Core parameter overrides
            overrides_tunable: Tunable parameter overrides
            
        Raises:
            ValueError: If version doesn't exist or is finalized
        """
        logger.info(f"Updating existing version {version} for {self.strategy_id}")
        
        # 1. Load full config
        config = self.load()
        versions = config.get("versions", {})
        
        # 2. Check version exists
        if version not in versions:
            raise ValueError(f"Version '{version}' not found for strategy '{self.strategy_id}'")
        
        # 3. Check if finalized
        version_node = versions[version]
        if version_node.get("strategy_finalized", False):
            raise ValueError(
                f"Cannot update finalized version '{version}'. "
                "Create a new version instead."
            )
        
        # 4. Apply overrides
        if overrides_core:
            version_node.setdefault("core", {}).update(overrides_core)
        if overrides_tunable:
            version_node.setdefault("tunable", {}).update(overrides_tunable)
        
        # 5. Validate
        self.validate(version, version_node)
        
        # 6. Write back atomically
        self.repository.write_strategy_file(self.strategy_id, config)
        
        logger.info(
            f"actions: config_version_updated strategy_id={self.strategy_id} "
            f"version={version} core_overrides={len(overrides_core or {})} "
            f"tunable_overrides={len(overrides_tunable or {})}"
        )

    def mark_as_finalized(self, version: str) -> None:
        """Mark a version as finalized (no further edits allowed).
        
        Args:
            version: Version to finalize
            
        Raises:
            ValueError: If version doesn't exist or already finalized
        """
        logger.info(f"Marking version {version} as finalized for {self.strategy_id}")
        
        # 1. Load full config
        config = self.load()
        versions = config.get("versions", {})
        
        # 2. Check version exists
        if version not in versions:
            raise ValueError(f"Version '{version}' not found for strategy '{self.strategy_id}'")
        
        # 3. Check if already finalized
        version_node = versions[version]
        if version_node.get("strategy_finalized", False):
            raise ValueError(f"Version '{version}' is already finalized")
        
        # 4. Set finalized flag
        version_node["strategy_finalized"] = True
        
        # 5. Write back atomically
        self.repository.write_strategy_file(self.strategy_id, config)
        
        logger.info(f"actions: config_version_finalized strategy_id={self.strategy_id} version={version}")

    def get_field_specs(self) -> Dict[str, Any]:
        """Return field specifications for UI rendering."""
        raise NotImplementedError("Subclasses must implement get_field_specs")
