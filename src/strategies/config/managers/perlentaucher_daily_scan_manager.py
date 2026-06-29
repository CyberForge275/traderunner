"""Config manager for perlentaucher_daily_scan strategy."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..manager_base import StrategyConfigManagerBase
from ..registry import config_manager_registry
from ..repository import StrategyConfigRepository
from ..specs.perlentaucher_daily_scan_spec import PerlentaucherDailyScanSpec


class PerlentaucherDailyScanConfigManager(StrategyConfigManagerBase):
    strategy_id = "perlentaucher_daily_scan"

    def __init__(self, repository=None):
        if repository is None:
            strategy_root = Path(__file__).resolve().parents[2] / "perlentaucher_daily_scan"
            repository = StrategyConfigRepository(base_path=strategy_root)
        super().__init__(repository=repository)
        self.spec = PerlentaucherDailyScanSpec()

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
    PerlentaucherDailyScanConfigManager.strategy_id,
    PerlentaucherDailyScanConfigManager(),
)
