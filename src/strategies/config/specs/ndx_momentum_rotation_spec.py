"""Ndx momentum rotation strategy parameter spec (skeleton)."""

from __future__ import annotations

from typing import Any, Dict


class NdxMomentumRotationSpec:
    REQUIRED_CORE_KEYS = {
        "session_timezone",
        "session_mode",
        "timeframe_minutes",
        "daily_universe",
        "daily_symbol_scope",
        "topk",
        "windows_months",
        "score_type",
        "momentum_skip_mode",
        "skip_last_n_weeks",
        "rebalance_equal_weight",
        "rebalance_frequency",
        "regime_filter",
        "risk_off_mode",
        "survivorship_mode",
        "min_history_months",
        "missing_data_policy",
        "sizing_mode",
        "cash_policy_on_gate_only",
    }

    ALLOWED_TUNABLE_KEYS: set[str] = set()

    SCORE_TYPES = {"sum_returns", "weighted", "twelve_only"}
    SKIP_MODES = {"none", "skip_last_month", "skip_last_n_weeks"}
    REGIME_FILTERS = {"qqq_sma200", "sp500_sma200", "breadth_ema_cross"}
    RISK_OFF_MODES = {"gate_only", "flat_all", "no_new_buys"}
    SURVIVORSHIP_MODES = {"pit_members", "current_members"}
    MISSING_DATA_POLICIES = {"FAIL_FAST", "SKIP_TICKER_MONTH"}
    SIZING_MODES = {"EQUAL_WEIGHT", "FIXED_NOTIONAL"}

    def validate_top_level(self, config: Dict[str, Any]) -> None:
        if "strategy_id" not in config or not isinstance(config["strategy_id"], str):
            raise ValueError("Missing/invalid top-level key: strategy_id")
        if "versions" not in config or not isinstance(config["versions"], dict):
            raise ValueError("Missing/invalid top-level key: versions")

    def validate_core(self, version: str, core: Dict[str, Any]) -> None:
        missing_keys = self.REQUIRED_CORE_KEYS - set(core.keys())
        if missing_keys:
            raise ValueError(
                f"ndx_momentum_rotation v{version} missing core key: {', '.join(sorted(missing_keys))}"
            )

        unknown_keys = set(core.keys()) - self.REQUIRED_CORE_KEYS
        if unknown_keys:
            raise ValueError(
                f"ndx_momentum_rotation v{version} unknown core key: {', '.join(sorted(unknown_keys))}"
            )

        session_timezone = core["session_timezone"]
        if not isinstance(session_timezone, str) or not session_timezone.strip():
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid session_timezone: {session_timezone!r}"
            )

        session_mode = core["session_mode"]
        if session_mode not in {"rth", "raw"}:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid session_mode: {session_mode!r}"
            )

        timeframe_minutes = core["timeframe_minutes"]
        if not isinstance(timeframe_minutes, int) or timeframe_minutes <= 0:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid timeframe_minutes: {timeframe_minutes!r}"
            )
        daily_universe = core["daily_universe"]
        if not isinstance(daily_universe, str) or not daily_universe.strip():
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid daily_universe: {daily_universe!r}"
            )

        daily_symbol_scope = core["daily_symbol_scope"]
        if not isinstance(daily_symbol_scope, str) or not daily_symbol_scope.strip():
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid daily_symbol_scope: {daily_symbol_scope!r}"
            )

        topk = core["topk"]
        if not isinstance(topk, int) or topk <= 0:
            raise ValueError(f"ndx_momentum_rotation v{version} invalid topk: {topk!r}")

        windows = core["windows_months"]
        if not isinstance(windows, list) or not windows or not all(
            isinstance(x, int) and x > 0 for x in windows
        ):
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid windows_months: {windows!r}"
            )

        score_type = core["score_type"]
        if score_type not in self.SCORE_TYPES:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid score_type: {score_type!r}"
            )

        skip_mode = core["momentum_skip_mode"]
        if skip_mode not in self.SKIP_MODES:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid momentum_skip_mode: {skip_mode!r}"
            )

        skip_weeks = core["skip_last_n_weeks"]
        if skip_weeks is not None and (
            not isinstance(skip_weeks, int) or skip_weeks < 1
        ):
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid skip_last_n_weeks: {skip_weeks!r}"
            )

        rebalance_equal_weight = core["rebalance_equal_weight"]
        if not isinstance(rebalance_equal_weight, bool):
            raise ValueError(
                f"ndx_momentum_rotation v{version} rebalance_equal_weight must be bool"
            )

        if core["rebalance_frequency"] != "monthly":
            raise ValueError(
                f"ndx_momentum_rotation v{version} rebalance_frequency must be 'monthly'"
            )

        regime_filter = core["regime_filter"]
        if regime_filter not in self.REGIME_FILTERS:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid regime_filter: {regime_filter!r}"
            )

        risk_off_mode = core["risk_off_mode"]
        if risk_off_mode not in self.RISK_OFF_MODES:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid risk_off_mode: {risk_off_mode!r}"
            )

        survivorship_mode = core["survivorship_mode"]
        if survivorship_mode not in self.SURVIVORSHIP_MODES:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid survivorship_mode: {survivorship_mode!r}"
            )

        min_history_months = core["min_history_months"]
        if not isinstance(min_history_months, int) or min_history_months < 1:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid min_history_months: {min_history_months!r}"
            )

        missing_data_policy = core["missing_data_policy"]
        if missing_data_policy not in self.MISSING_DATA_POLICIES:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid missing_data_policy: {missing_data_policy!r}"
            )

        sizing_mode = core["sizing_mode"]
        if sizing_mode not in self.SIZING_MODES:
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid sizing_mode: {sizing_mode!r}"
            )

        cash_policy = core["cash_policy_on_gate_only"]
        if not isinstance(cash_policy, str) or not cash_policy.strip():
            raise ValueError(
                f"ndx_momentum_rotation v{version} invalid cash_policy_on_gate_only: {cash_policy!r}"
            )

    def validate_tunable(self, version: str, tunable: Dict[str, Any]) -> None:
        unknown_keys = set(tunable.keys()) - self.ALLOWED_TUNABLE_KEYS
        if unknown_keys:
            raise ValueError(
                f"ndx_momentum_rotation v{version} unknown tunable key: {', '.join(sorted(unknown_keys))}"
            )

    def get_field_specs(self) -> Dict[str, Any]:
        return {
            "core": {
                "session_timezone": {"kind": "string", "required": True},
                "session_mode": {
                    "kind": "enum",
                    "required": True,
                    "options": ["rth", "raw"],
                },
                "timeframe_minutes": {"kind": "int", "required": True, "min": 1},
                "daily_universe": {"kind": "string", "required": True},
                "daily_symbol_scope": {"kind": "string", "required": True},
                "topk": {"kind": "int", "required": True, "min": 1},
                "windows_months": {"kind": "string", "required": True},
                "score_type": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.SCORE_TYPES),
                },
                "momentum_skip_mode": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.SKIP_MODES),
                },
                "skip_last_n_weeks": {"kind": "int", "required": False, "min": 1},
                "rebalance_equal_weight": {"kind": "bool", "required": True},
                "rebalance_frequency": {
                    "kind": "enum",
                    "required": True,
                    "options": ["monthly"],
                },
                "regime_filter": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.REGIME_FILTERS),
                },
                "risk_off_mode": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.RISK_OFF_MODES),
                },
                "survivorship_mode": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.SURVIVORSHIP_MODES),
                },
                "min_history_months": {"kind": "int", "required": True, "min": 1},
                "missing_data_policy": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.MISSING_DATA_POLICIES),
                },
                "sizing_mode": {
                    "kind": "enum",
                    "required": True,
                    "options": sorted(self.SIZING_MODES),
                },
                "cash_policy_on_gate_only": {"kind": "string", "required": True},
            },
            "tunable": {},
        }
