"""Confirmed Breakout config manager wired into SSOT manager registry."""

from pathlib import Path
from typing import Any, Dict

from ..manager_base import StrategyConfigManagerBase
from ..repository import StrategyConfigRepository
from ..specs.inside_bar_spec import InsideBarSpec


class ConfirmedBreakoutConfigManager(StrategyConfigManagerBase):
    """Config manager for confirmed breakout strategy."""

    strategy_id = "confirmed_breakout_intraday"

    def __init__(self, repository=None):
        if repository is None:
            strategy_root = Path(__file__).resolve().parents[2] / "confirmed_breakout"
            repository = StrategyConfigRepository(base_path=strategy_root)
        super().__init__(repository=repository)
        self.spec = InsideBarSpec()

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
    ConfirmedBreakoutConfigManager.strategy_id,
    ConfirmedBreakoutConfigManager(),
)
