"""Parameter spec for perlentaucher_daily_scan skeleton."""

from __future__ import annotations

from typing import Any, Dict


class PerlentaucherDailyScanSpec:
    REQUIRED_CORE_KEYS = {
        "enabled",
        "timeframe_minutes",
        "match_mode",
        "use_volume_prefilter",
        "reference_set",
        "min_history_days",
        "max_candidates",
    }

    MATCH_MODES = {"price_vol", "zscore"}
    REFERENCE_SETS = {"default"}

    def validate_top_level(self, config: Dict[str, Any]) -> None:
        if "strategy_id" not in config or not isinstance(config["strategy_id"], str):
            raise ValueError("Missing/invalid top-level key: strategy_id")
        if "versions" not in config or not isinstance(config["versions"], dict):
            raise ValueError("Missing/invalid top-level key: versions")

    def validate_core(self, version: str, core: Dict[str, Any]) -> None:
        missing = self.REQUIRED_CORE_KEYS - set(core.keys())
        if missing:
            raise ValueError(
                "perlentaucher_daily_scan "
                f"v{version} missing core key: {', '.join(sorted(missing))}"
            )

        unknown = set(core.keys()) - self.REQUIRED_CORE_KEYS
        if unknown:
            raise ValueError(
                "perlentaucher_daily_scan "
                f"v{version} unknown core key: {', '.join(sorted(unknown))}"
            )

        if not isinstance(core["enabled"], bool):
            raise ValueError(f"perlentaucher_daily_scan v{version} enabled must be bool")
        if core["timeframe_minutes"] != 1440:
            raise ValueError(
                f"perlentaucher_daily_scan v{version} invalid timeframe_minutes: {core['timeframe_minutes']!r}"
            )
        if core["match_mode"] not in self.MATCH_MODES:
            raise ValueError(
                f"perlentaucher_daily_scan v{version} invalid match_mode: {core['match_mode']!r}"
            )
        if not isinstance(core["use_volume_prefilter"], bool):
            raise ValueError(
                f"perlentaucher_daily_scan v{version} use_volume_prefilter must be bool"
            )
        if core["reference_set"] not in self.REFERENCE_SETS:
            raise ValueError(
                f"perlentaucher_daily_scan v{version} invalid reference_set: {core['reference_set']!r}"
            )
        if not isinstance(core["min_history_days"], int) or core["min_history_days"] < 107:
            raise ValueError(
                f"perlentaucher_daily_scan v{version} invalid min_history_days: {core['min_history_days']!r}"
            )
        if not isinstance(core["max_candidates"], int) or core["max_candidates"] <= 0:
            raise ValueError(
                f"perlentaucher_daily_scan v{version} invalid max_candidates: {core['max_candidates']!r}"
            )

    def validate_tunable(self, version: str, tunable: Dict[str, Any]) -> None:
        if tunable:
            raise ValueError(
                f"perlentaucher_daily_scan v{version} unknown tunable key: {', '.join(sorted(tunable.keys()))}"
            )

    def get_field_specs(self) -> Dict[str, Any]:
        return {
            "core": {
                "enabled": {"kind": "bool", "required": True},
                "timeframe_minutes": {"kind": "int", "required": True, "min": 1440, "max": 1440},
                "match_mode": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.MATCH_MODES),
                },
                "use_volume_prefilter": {"kind": "bool", "required": True},
                "reference_set": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.REFERENCE_SETS),
                },
                "min_history_days": {"kind": "int", "required": True, "min": 107},
                "max_candidates": {"kind": "int", "required": True, "min": 1},
            },
            "tunable": {},
        }
