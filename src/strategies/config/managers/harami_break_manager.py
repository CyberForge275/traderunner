"""Harami Break config manager wired into SSOT manager registry."""

from pathlib import Path
from typing import Any, Dict

from ..manager_base import StrategyConfigManagerBase
from ..repository import StrategyConfigRepository
from ..specs.harami_break_spec import HaramiBreakSpec


class HaramiBreakConfigManager(StrategyConfigManagerBase):
    """Config manager for harami break strategy."""

    strategy_id = "harami_break_intraday"

    def __init__(self, repository=None):
        if repository is None:
            strategy_root = Path(__file__).resolve().parents[2] / "harami_break"
            repository = StrategyConfigRepository(base_path=strategy_root)
        super().__init__(repository=repository)
        self.spec = HaramiBreakSpec()

    def extra_allowed_version_keys(self) -> set[str]:
        return {"signal_schema_ref"}

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


from ..registry import config_manager_registry

config_manager_registry.register(
    HaramiBreakConfigManager.strategy_id,
    HaramiBreakConfigManager(),
)
