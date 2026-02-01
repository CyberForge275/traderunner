"""Strategy Config Repository - Handles path resolution and file reading for SSOT YAMLs."""

import os
import tempfile
from pathlib import Path
import yaml
from typing import Dict, Any, Optional


class StrategyConfigRepository:
    """Repository for strategy configuration files."""

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize repository.
        
        Args:
            base_path: Optional override. If not set, resolves via ENV or default.
        """
        self._explicit_base_path = Path(base_path) if base_path else None

    @property
    def base_path(self) -> Path:
        """Resolve base path lazily to support ENV overrides in tests."""
        if self._explicit_base_path:
            return self._explicit_base_path
            
        # Priority: ENV > Default
        env_path = os.getenv("STRATEGY_CONFIG_ROOT")
        if env_path:
            return Path(env_path)
            
        # Default to inside_bar strategy directory (SSOT)
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        return project_root / "src" / "strategies" / "inside_bar"

    def read_strategy_file(self, strategy_name: str) -> Dict[str, Any]:
        """
        Read and parse YAML file for a strategy.
        
        Args:
            strategy_name: Name of the strategy (e.g. 'inside_bar')
            
        Returns:
            Parsed YAML as dictionary
            
        Raises:
            FileNotFoundError: If the YAML file does not exist
            yaml.YAMLError: If parsing fails
        """
        file_path = self.base_path / f"{strategy_name}.yaml"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Strategy config file not found: {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def write_strategy_file(self, strategy_id: str, content: Dict[str, Any]) -> None:
        """
        Atomically write strategy YAML file (crash-safe: tmp + rename).
        
        Args:
            strategy_id: Strategy identifier (must match content["strategy_id"])
            content: Full YAML content as dictionary
            
        Raises:
            ValueError: If strategy_id mismatch or invalid content
            OSError: If write fails
        """
        # 1. Validate strategy_id match
        if content.get("strategy_id") != strategy_id:
            raise ValueError(
                f"Strategy ID mismatch: filename expects '{strategy_id}', "
                f"content has '{content.get('strategy_id')}'"
            )
        
        # 2. Ensure base_path exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        target_path = self.base_path / f"{strategy_id}.yaml"
        
        # 3. Atomic write: tmp file + rename
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.base_path,
            prefix=f".{strategy_id}_",
            suffix=".yaml.tmp"
        )
        
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                yaml.dump(content, f, default_flow_style=False, sort_keys=False)
            
            # 4. Validate tmp file is parseable
            with open(tmp_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
            
            # 5. Atomic rename
            os.replace(tmp_path, target_path)
            
        except Exception:
            # Cleanup tmp file on failure
            if Path(tmp_path).exists():
                os.unlink(tmp_path)
            raise
