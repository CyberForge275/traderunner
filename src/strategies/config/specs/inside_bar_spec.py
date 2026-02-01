"""InsideBar Configuration Specification - Defines schema and validation rules."""

from typing import Dict, Any, List


class InsideBarSpec:
    """Specification for InsideBar strategy parameters."""
    
    REQUIRED_CORE_KEYS = {
        "atr_period",
        "risk_reward_ratio",
        "min_mother_bar_size",
        "breakout_confirmation",
        "inside_bar_mode",
        "session_timezone",
        "session_mode",
        "session_filter",
        "timeframe_minutes",
        "valid_from_policy",
        "order_validity_policy",
        "stop_distance_cap_ticks",
        "max_position_pct",
    }
    
    ALLOWED_TUNABLE_KEYS = {
        "lookback_candles",
        "max_pattern_age_candles",
        "max_deviation_atr",
        "max_position_loss_pct_equity"
    }
    
    ALLOWED_MODES = {"inclusive", "strict"}
    VALID_FROM_POLICY_OPTIONS = ("signal_ts", "next_bar")
    ORDER_VALIDITY_POLICY_OPTIONS = ("session_end", "one_bar", "fixed_minutes")

    def validate_top_level(self, config: Dict[str, Any]) -> None:
        """Validate top-level YAML structure."""
        # 1. strategy_id
        if "strategy_id" not in config:
            raise ValueError("Missing top-level key: strategy_id")
        if not isinstance(config["strategy_id"], str):
            raise ValueError("strategy_id must be a string")
            
        # 2. versions
        if "versions" not in config:
            raise ValueError("Missing top-level key: versions")
        if not isinstance(config["versions"], dict):
            raise ValueError("versions must be a dictionary")
            
        # 3. Version keys must be strings
        for v_key in config["versions"].keys():
            if not isinstance(v_key, str):
                raise ValueError(f"Version key '{v_key}' must be a string")

    def validate_core(self, version: str, core: Dict[str, Any]) -> None:
        """Validate core parameters."""
        # 1. Check missing keys
        missing_keys = self.REQUIRED_CORE_KEYS - set(core.keys())
        if missing_keys:
            raise ValueError(
                f"inside_bar v{version} missing core key: {', '.join(sorted(missing_keys))}"
            )
            
        # 2. Check unknown keys in core
        unknown_keys = set(core.keys()) - self.REQUIRED_CORE_KEYS
        if unknown_keys:
            raise ValueError(
                f"inside_bar v{version} unknown core key: {', '.join(sorted(unknown_keys))}"
            )
            
        # 3. Type and value checks
        self._validate_types(version, "core", core)
        
    def validate_tunable(self, version: str, tunable: Dict[str, Any]) -> None:
        """Validate tunable parameters."""
        # 1. Check unknown keys in tunable
        unknown_keys = set(tunable.keys()) - self.ALLOWED_TUNABLE_KEYS
        if unknown_keys:
            raise ValueError(
                f"inside_bar v{version} unknown tunable key: {', '.join(sorted(unknown_keys))}"
            )
            
        # 2. Type and value checks
        self._validate_types(version, "tunable", tunable)

    def _validate_types(self, version: str, block: str, data: Dict[str, Any]) -> None:
        """Helper to validate types and ranges for InsideBar."""
        
        # atr_period: int >= 1
        if "atr_period" in data:
            val = data["atr_period"]
            if not isinstance(val, int) or val < 1:
                raise ValueError(f"inside_bar v{version} invalid atr_period: {val} (must be int >= 1)")

        # risk_reward_ratio: float > 0
        if "risk_reward_ratio" in data:
            val = data["risk_reward_ratio"]
            if not isinstance(val, (int, float)) or val <= 0:
                raise ValueError(f"inside_bar v{version} invalid risk_reward_ratio: {val} (must be float > 0)")

        # min_mother_bar_size: float >= 0
        if "min_mother_bar_size" in data:
            val = data["min_mother_bar_size"]
            if not isinstance(val, (int, float)) or val < 0:
                raise ValueError(f"inside_bar v{version} invalid min_mother_bar_size: {val} (must be float >= 0)")

        # breakout_confirmation: bool
        if "breakout_confirmation" in data:
            val = data["breakout_confirmation"]
            if not isinstance(val, bool):
                raise ValueError(f"inside_bar v{version} invalid breakout_confirmation: {val} (must be bool)")

        # inside_bar_mode: string in enum
        if "inside_bar_mode" in data:
            val = data["inside_bar_mode"]
            if val not in self.ALLOWED_MODES:
                raise ValueError(
                    f"inside_bar v{version} invalid inside_bar_mode: {val} "
                    f"(allowed: {', '.join(sorted(self.ALLOWED_MODES))})"
                )

        # lookback_candles: int >= 1
        if "lookback_candles" in data:
            val = data["lookback_candles"]
            if not isinstance(val, int) or val < 1:
                raise ValueError(f"inside_bar v{version} invalid lookback_candles: {val} (must be int >= 1)")

        # max_pattern_age_candles: int >= 1
        if "max_pattern_age_candles" in data:
            val = data["max_pattern_age_candles"]
            if not isinstance(val, int) or val < 1:
                raise ValueError(f"inside_bar v{version} invalid max_pattern_age_candles: {val} (must be int >= 1)")

        # max_deviation_atr: float >= 0
        if "max_deviation_atr" in data:
            val = data["max_deviation_atr"]
            if not isinstance(val, (int, float)) or val < 0:
                raise ValueError(f"inside_bar v{version} invalid max_deviation_atr: {val} (must be float >= 0)")

        # max_position_loss_pct_equity: float > 0 and <= 1
        if "max_position_loss_pct_equity" in data:
            val = data["max_position_loss_pct_equity"]
            if not isinstance(val, (int, float)) or val <= 0 or val > 1:
                raise ValueError(f"inside_bar v{version} invalid max_position_loss_pct_equity: {val} (must be float > 0 and <= 1)")

        # session_timezone: str
        if "session_timezone" in data:
            val = data["session_timezone"]
            if not isinstance(val, str):
                raise ValueError(f"inside_bar v{version} invalid session_timezone: {val} (must be str)")

        # session_filter: list of strings
        if "session_filter" in data:
            val = data["session_filter"]
            if not isinstance(val, list) or not all(isinstance(s, str) for s in val):
                raise ValueError(f"inside_bar v{version} invalid session_filter: {val} (must be list of str)")

        # timeframe_minutes: int > 0
        if "timeframe_minutes" in data:
            val = data["timeframe_minutes"]
            if not isinstance(val, int) or val <= 0:
                raise ValueError(f"inside_bar v{version} invalid timeframe_minutes: {val} (must be int > 0)")

        # valid_from_policy: str
        if "valid_from_policy" in data:
            val = data["valid_from_policy"]
            if val not in self.VALID_FROM_POLICY_OPTIONS:
                raise ValueError(
                    f"inside_bar v{version} invalid valid_from_policy: '{val}' "
                    f"(allowed: {', '.join(self.VALID_FROM_POLICY_OPTIONS)})"
                )
        
        # order_validity_policy: str
        if "order_validity_policy" in data:
            val = data["order_validity_policy"]
            if val not in self.ORDER_VALIDITY_POLICY_OPTIONS:
                raise ValueError(
                    f"inside_bar v{version} invalid order_validity_policy: '{val}' "
                    f"(allowed: {', '.join(self.ORDER_VALIDITY_POLICY_OPTIONS)})"
                )

        if "session_mode" in data:
            val = data["session_mode"]
            if val not in {"rth", "raw"}:
                raise ValueError(
                    f"inside_bar v{version} invalid session_mode: {val} (allowed: rth, raw)"
                )

        # stop_distance_cap_ticks: int > 0
        if "stop_distance_cap_ticks" in data:
            val = data["stop_distance_cap_ticks"]
            if not isinstance(val, int) or val <= 0:
                raise ValueError(
                    f"inside_bar v{version} invalid stop_distance_cap_ticks: {val} (must be int > 0)"
                )

        # max_position_pct: float > 0 and <= 100
        if "max_position_pct" in data:
            val = data["max_position_pct"]
            if not isinstance(val, (int, float)) or val <= 0 or val > 100:
                raise ValueError(
                    f"inside_bar v{version} invalid max_position_pct: {val} (must be float > 0 and <= 100)"
                )

    def get_field_specs(self) -> Dict[str, Any]:
        """Return field specifications for UI rendering."""
        return {
            "core": {
                "atr_period": {"kind": "int", "required": True, "min": 1},
                "risk_reward_ratio": {"kind": "float", "required": True, "min": 0.1},
                "min_mother_bar_size": {"kind": "float", "required": True, "min": 0.0},
                "breakout_confirmation": {"kind": "bool", "required": True},
                "inside_bar_mode": {
                    "kind": "enum",
                    "options": list(self.ALLOWED_MODES),
                    "required": True
                },
                "session_timezone": {"kind": "string", "required": True},
                "session_filter": {"kind": "string", "required": True},  # Rendered as string in UI
                "timeframe_minutes": {"kind": "int", "required": True, "min": 1},
                "valid_from_policy": {
                    "kind": "enum",
                    "options": list(self.VALID_FROM_POLICY_OPTIONS),
                    "required": True
                },
                "order_validity_policy": {
                    "kind": "enum",
                    "options": list(self.ORDER_VALIDITY_POLICY_OPTIONS),
                    "required": True
                },
                "stop_distance_cap_ticks": {"kind": "int", "required": True, "min": 1},
                "max_position_pct": {"kind": "float", "required": True, "min": 0.0, "max": 100.0},
            },
            "tunable": {
                "lookback_candles": {"kind": "int", "required": True, "min": 1},
                "max_pattern_age_candles": {"kind": "int", "required": True, "min": 1},
                "max_deviation_atr": {"kind": "float", "required": True, "min": 0.0},
                "max_position_loss_pct_equity": {"kind": "float", "required": False, "min": 0.0, "max": 1.0},
            }
        }
