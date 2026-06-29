"""Config manager for ndx_momentum_rotation strategy."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..manager_base import StrategyConfigManagerBase
from ..registry import config_manager_registry
from ..repository import StrategyConfigRepository
from ..specs.ndx_momentum_rotation_spec import NdxMomentumRotationSpec


class NdxMomentumRotationConfigManager(StrategyConfigManagerBase):
    strategy_id = "ndx_momentum_rotation"

    def __init__(self, repository=None):
        if repository is None:
            strategy_root = Path(__file__).resolve().parents[2] / "ndx_momentum_rotation"
            repository = StrategyConfigRepository(base_path=strategy_root)
        super().__init__(repository=repository)
        self.spec = NdxMomentumRotationSpec()

    def requires_warmup_bars(self) -> bool:
        return False

    def get(self, version: str) -> Dict[str, Any]:
        return self.get_version(version)

    def validate(self, version: str, node: Dict[str, Any]) -> None:
        super().validate(version, node)
        self.spec.validate_core(version, node["core"])
        if "tunable" in node:
            self.spec.validate_tunable(version, node["tunable"])

    def get_metadata(self) -> Dict[str, Any]:
        config = self.load()
        self.spec.validate_top_level(config)
        return {
            "strategy_id": config.get("strategy_id"),
            "canonical_name": config.get("canonical_name"),
            "versions": list(config.get("versions", {}).keys()),
        }

    def get_field_specs(self) -> Dict[str, Any]:
        return self.spec.get_field_specs()


config_manager_registry.register(
    NdxMomentumRotationConfigManager.strategy_id,
    NdxMomentumRotationConfigManager(),
)
