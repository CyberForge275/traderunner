"""Confirmed Breakout configuration spec extending InsideBar fields."""

from typing import Any, Dict

from .inside_bar_spec import InsideBarSpec


class ConfirmedBreakoutSpec(InsideBarSpec):
    """InsideBar-compatible spec plus confirmed breakout tunables."""

    ALLOWED_TUNABLE_KEYS = InsideBarSpec.ALLOWED_TUNABLE_KEYS | {
        "mother_range_ratio_min",
        "mother_range_ratio_max",
    }

    def _validate_types(self, version: str, block: str, data: Dict[str, Any]) -> None:
        super()._validate_types(version, block, data)

        if "mother_range_ratio_min" in data:
            val = data["mother_range_ratio_min"]
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"confirmed_breakout v{version} invalid mother_range_ratio_min: {val} (must be float)"
                )

        if "mother_range_ratio_max" in data:
            val = data["mother_range_ratio_max"]
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"confirmed_breakout v{version} invalid mother_range_ratio_max: {val} (must be float)"
                )

        if "mother_range_ratio_min" in data and "mother_range_ratio_max" in data:
            min_rr = float(data["mother_range_ratio_min"])
            max_rr = float(data["mother_range_ratio_max"])
            if not (0 < min_rr < max_rr <= 1.5):
                raise ValueError(
                    f"confirmed_breakout v{version} invalid ratio band: min={min_rr}, max={max_rr} "
                    "(must satisfy 0 < min < max <= 1.5)"
                )

    def get_field_specs(self) -> Dict[str, Any]:
        specs = super().get_field_specs()
        specs.setdefault("tunable", {})
        specs["tunable"]["mother_range_ratio_min"] = {
            "kind": "float",
            "required": False,
            "min": 0.0,
            "max": 1.5,
        }
        specs["tunable"]["mother_range_ratio_max"] = {
            "kind": "float",
            "required": False,
            "min": 0.0,
            "max": 1.5,
        }
        return specs
