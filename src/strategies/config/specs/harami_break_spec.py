"""Harami Break configuration specification."""

from typing import Any, Dict


class HaramiBreakSpec:
    """Specification for Harami Break strategy parameters."""

    REQUIRED_CORE_KEYS = {
        "session_timezone",
        "session_mode",
        "timeframe_minutes",
        "session_windows",
        "inside_bar_definition_mode",
        "strict_mode",
        "entry_level_mode",
        "max_trades_per_session_window",
        "order_validity_policy",
        "order_validity_minutes",
        "order_validity_bars",
        "trailing",
    }

    ALLOWED_TUNABLE_KEYS: set[str] = set()

    ALLOWED_DEFINITION_MODES = {
        "mb_body_oc__ib_hl",
        "mb_body_oc__ib_body",
        "mb_range_hl__ib_hl",
        "mb_high__ib_high_and_close_in_mb_range",
    }
    ALLOWED_ENTRY_LEVEL_MODES = {"mother_bar", "inside_bar"}
    ALLOWED_ORDER_VALIDITY_POLICIES = {"session_end", "fixed_minutes", "fixed_bars"}
    ALLOWED_TRAILING_APPLY_MODES = {"next_bar", "same_bar"}
    SESSION_TIMEZONE_OPTIONS = {"America/New_York", "Europe/Berlin"}
    SESSION_MODE_OPTIONS = {"rth", "raw"}

    def validate_top_level(self, config: Dict[str, Any]) -> None:
        if "strategy_id" not in config or not isinstance(config["strategy_id"], str):
            raise ValueError("Missing/invalid top-level key: strategy_id")
        if "versions" not in config or not isinstance(config["versions"], dict):
            raise ValueError("Missing/invalid top-level key: versions")

    def validate_core(self, version: str, core: Dict[str, Any]) -> None:
        missing_keys = self.REQUIRED_CORE_KEYS - set(core.keys())
        if missing_keys:
            raise ValueError(
                f"harami_break v{version} missing core key: {', '.join(sorted(missing_keys))}"
            )

        unknown_keys = set(core.keys()) - self.REQUIRED_CORE_KEYS
        if unknown_keys:
            raise ValueError(
                f"harami_break v{version} unknown core key: {', '.join(sorted(unknown_keys))}"
            )

        self._validate_types(version, core)

    def validate_tunable(self, version: str, tunable: Dict[str, Any]) -> None:
        unknown_keys = set(tunable.keys()) - self.ALLOWED_TUNABLE_KEYS
        if unknown_keys:
            raise ValueError(
                f"harami_break v{version} unknown tunable key: {', '.join(sorted(unknown_keys))}"
            )

    def _validate_types(self, version: str, data: Dict[str, Any]) -> None:
        timezone = data["session_timezone"]
        if timezone not in self.SESSION_TIMEZONE_OPTIONS:
            raise ValueError(
                f"harami_break v{version} invalid session_timezone: {timezone!r} "
                f"(allowed: {sorted(self.SESSION_TIMEZONE_OPTIONS)})"
            )

        windows = data["session_windows"]
        if not isinstance(windows, list) or not windows or not all(isinstance(s, str) and "-" in s for s in windows):
            raise ValueError(
                f"harami_break v{version} invalid session_windows: {windows!r} (must be list of 'HH:MM-HH:MM')"
            )
        mode = data["session_mode"]
        if mode not in self.SESSION_MODE_OPTIONS:
            raise ValueError(
                f"harami_break v{version} invalid session_mode: {mode!r} "
                f"(allowed: {sorted(self.SESSION_MODE_OPTIONS)})"
            )
        tf = data["timeframe_minutes"]
        if not isinstance(tf, int) or tf <= 0:
            raise ValueError(
                f"harami_break v{version} invalid timeframe_minutes: {tf!r} (must be int > 0)"
            )

        definition_mode = data["inside_bar_definition_mode"]
        if definition_mode not in self.ALLOWED_DEFINITION_MODES:
            raise ValueError(
                f"harami_break v{version} invalid inside_bar_definition_mode: {definition_mode!r} "
                f"(allowed: {sorted(self.ALLOWED_DEFINITION_MODES)})"
            )
        strict_mode = data["strict_mode"]
        if not isinstance(strict_mode, bool):
            raise ValueError(f"harami_break v{version} invalid strict_mode: {strict_mode!r} (must be bool)")

        entry_level_mode = data["entry_level_mode"]
        if entry_level_mode not in self.ALLOWED_ENTRY_LEVEL_MODES:
            raise ValueError(
                f"harami_break v{version} invalid entry_level_mode: {entry_level_mode!r} "
                f"(allowed: {sorted(self.ALLOWED_ENTRY_LEVEL_MODES)})"
            )

        max_trades = data["max_trades_per_session_window"]
        if not isinstance(max_trades, int) or max_trades < 1:
            raise ValueError(
                f"harami_break v{version} invalid max_trades_per_session_window: {max_trades!r} (must be int >= 1)"
            )

        validity = data["order_validity_policy"]
        if validity not in self.ALLOWED_ORDER_VALIDITY_POLICIES:
            raise ValueError(
                f"harami_break v{version} invalid order_validity_policy: {validity!r} "
                f"(allowed: {sorted(self.ALLOWED_ORDER_VALIDITY_POLICIES)})"
            )
        validity_minutes = data["order_validity_minutes"]
        if not isinstance(validity_minutes, int) or validity_minutes < 1 or validity_minutes > 60:
            raise ValueError(
                f"harami_break v{version} invalid order_validity_minutes: {validity_minutes!r} (must be int in [1,60])"
            )
        validity_bars = data["order_validity_bars"]
        if not isinstance(validity_bars, int) or validity_bars < 1 or validity_bars > 10:
            raise ValueError(
                f"harami_break v{version} invalid order_validity_bars: {validity_bars!r} (must be int in [1,10])"
            )

        trailing = data["trailing"]
        if not isinstance(trailing, dict):
            raise ValueError(f"harami_break v{version} trailing must be a mapping")
        required_trailing = {"enabled", "trigger_tp_pct", "risk_remaining_pct", "apply_mode"}
        missing_trailing = required_trailing - set(trailing.keys())
        if missing_trailing:
            raise ValueError(
                f"harami_break v{version} trailing missing key: {', '.join(sorted(missing_trailing))}"
            )

        enabled = trailing["enabled"]
        if not isinstance(enabled, bool):
            raise ValueError(f"harami_break v{version} trailing.enabled must be bool")

        trigger = trailing["trigger_tp_pct"]
        if not isinstance(trigger, (int, float)) or float(trigger) <= 0:
            raise ValueError(
                f"harami_break v{version} invalid trailing.trigger_tp_pct: {trigger!r} (must be float > 0)"
            )

        remaining = trailing["risk_remaining_pct"]
        if not isinstance(remaining, (int, float)) or float(remaining) < 0:
            raise ValueError(
                f"harami_break v{version} invalid trailing.risk_remaining_pct: {remaining!r} (must be float >= 0)"
            )

        apply_mode = trailing["apply_mode"]
        if apply_mode not in self.ALLOWED_TRAILING_APPLY_MODES:
            raise ValueError(
                f"harami_break v{version} invalid trailing.apply_mode: {apply_mode!r} "
                f"(allowed: {sorted(self.ALLOWED_TRAILING_APPLY_MODES)})"
            )

    def get_field_specs(self) -> Dict[str, Any]:
        return {
            "core": {
                "session_timezone": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.SESSION_TIMEZONE_OPTIONS),
                },
                "session_windows": {"kind": "string", "required": True},
                "session_mode": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.SESSION_MODE_OPTIONS),
                },
                "timeframe_minutes": {"kind": "int", "required": True, "min": 1},
                "inside_bar_definition_mode": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.ALLOWED_DEFINITION_MODES),
                },
                "strict_mode": {"kind": "bool", "required": True},
                "entry_level_mode": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.ALLOWED_ENTRY_LEVEL_MODES),
                },
                "max_trades_per_session_window": {"kind": "int", "required": True, "min": 1},
                "order_validity_policy": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.ALLOWED_ORDER_VALIDITY_POLICIES),
                },
                "order_validity_minutes": {"kind": "int", "required": True, "min": 1, "max": 60},
                "order_validity_bars": {"kind": "int", "required": True, "min": 1, "max": 10},
                "trailing": {"kind": "json", "required": True},
            },
            "tunable": {},
        }
