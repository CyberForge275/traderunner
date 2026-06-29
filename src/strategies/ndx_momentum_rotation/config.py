"""Typed configuration contract for ndx_momentum_rotation skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ScoreType(str, Enum):
    SUM_RETURNS = "sum_returns"
    WEIGHTED = "weighted"
    TWELVE_ONLY = "twelve_only"


class MomentumSkipMode(str, Enum):
    NONE = "none"
    SKIP_LAST_MONTH = "skip_last_month"
    SKIP_LAST_N_WEEKS = "skip_last_n_weeks"


class RegimeFilterType(str, Enum):
    QQQ_SMA200 = "qqq_sma200"
    SP500_SMA200 = "sp500_sma200"
    BREADTH_EMA_CROSS = "breadth_ema_cross"


class RiskOffMode(str, Enum):
    GATE_ONLY = "gate_only"
    FLAT_ALL = "flat_all"
    NO_NEW_BUYS = "no_new_buys"


class SurvivorshipMode(str, Enum):
    PIT_MEMBERS = "pit_members"
    CURRENT_MEMBERS = "current_members"


class MissingDataPolicy(str, Enum):
    FAIL_FAST = "FAIL_FAST"
    SKIP_TICKER_MONTH = "SKIP_TICKER_MONTH"


class SizingMode(str, Enum):
    EQUAL_WEIGHT = "EQUAL_WEIGHT"
    FIXED_NOTIONAL = "FIXED_NOTIONAL"


@dataclass(frozen=True)
class NdxMomentumRotationConfig:
    session_timezone: str
    session_mode: str
    timeframe_minutes: int
    daily_universe: str
    daily_symbol_scope: str
    topk: int
    windows_months: list[int]
    score_type: ScoreType
    momentum_skip_mode: MomentumSkipMode
    skip_last_n_weeks: int | None
    rebalance_equal_weight: bool
    rebalance_frequency: str
    regime_filter: RegimeFilterType
    risk_off_mode: RiskOffMode
    survivorship_mode: SurvivorshipMode
    min_history_months: int
    missing_data_policy: MissingDataPolicy
    sizing_mode: SizingMode
    cash_policy_on_gate_only: str


def _as_enum(value: Any, enum_cls: type[Enum], field: str) -> Enum:
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = sorted([member.value for member in enum_cls])
        raise ValueError(f"invalid {field}: {value!r} (allowed: {allowed})") from exc


def build_ndx_momentum_rotation_config(params: dict[str, Any]) -> NdxMomentumRotationConfig:
    """Build strict strategy config from params mapping (no hidden defaults)."""

    required_keys = {
        "session_timezone",
        "session_mode",
        "timeframe_minutes",
        "daily_universe",
        "daily_symbol_scope",
        "topk",
        "windows_months",
        "score_type",
        "momentum_skip_mode",
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
    missing = sorted(required_keys - set(params.keys()))
    if missing:
        raise ValueError(
            "ndx_momentum_rotation missing required config keys: " + ", ".join(missing)
        )

    windows_months = params["windows_months"]
    if not isinstance(windows_months, list) or not windows_months:
        raise ValueError("windows_months must be a non-empty list[int]")
    if not all(isinstance(x, int) and x > 0 for x in windows_months):
        raise ValueError("windows_months entries must be int > 0")

    topk = params["topk"]
    if not isinstance(topk, int) or topk <= 0:
        raise ValueError("topk must be int > 0")

    min_history_months = params["min_history_months"]
    if not isinstance(min_history_months, int) or min_history_months < 1:
        raise ValueError("min_history_months must be int >= 1")

    skip_last_n_weeks = params.get("skip_last_n_weeks")
    if skip_last_n_weeks is not None and (
        not isinstance(skip_last_n_weeks, int) or skip_last_n_weeks < 1
    ):
        raise ValueError("skip_last_n_weeks must be null or int >= 1")

    rebalance_frequency = str(params["rebalance_frequency"])
    if rebalance_frequency != "monthly":
        raise ValueError("rebalance_frequency must be 'monthly' in skeleton")

    session_timezone = str(params["session_timezone"])
    if not session_timezone:
        raise ValueError("session_timezone must be a non-empty string")
    session_mode = str(params["session_mode"])
    if session_mode not in {"rth", "raw"}:
        raise ValueError("session_mode must be one of ['raw', 'rth']")
    timeframe_minutes = params["timeframe_minutes"]
    if not isinstance(timeframe_minutes, int) or timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be int > 0")
    daily_universe = str(params["daily_universe"]).upper()
    if not daily_universe:
        raise ValueError("daily_universe must be a non-empty string")
    daily_symbol_scope = str(params["daily_symbol_scope"]).upper()
    if not daily_symbol_scope:
        raise ValueError("daily_symbol_scope must be a non-empty string")

    return NdxMomentumRotationConfig(
        session_timezone=session_timezone,
        session_mode=session_mode,
        timeframe_minutes=timeframe_minutes,
        daily_universe=daily_universe,
        daily_symbol_scope=daily_symbol_scope,
        topk=topk,
        windows_months=windows_months,
        score_type=_as_enum(params["score_type"], ScoreType, "score_type"),
        momentum_skip_mode=_as_enum(
            params["momentum_skip_mode"], MomentumSkipMode, "momentum_skip_mode"
        ),
        skip_last_n_weeks=skip_last_n_weeks,
        rebalance_equal_weight=bool(params["rebalance_equal_weight"]),
        rebalance_frequency=rebalance_frequency,
        regime_filter=_as_enum(params["regime_filter"], RegimeFilterType, "regime_filter"),
        risk_off_mode=_as_enum(params["risk_off_mode"], RiskOffMode, "risk_off_mode"),
        survivorship_mode=_as_enum(
            params["survivorship_mode"], SurvivorshipMode, "survivorship_mode"
        ),
        min_history_months=min_history_months,
        missing_data_policy=_as_enum(
            params["missing_data_policy"], MissingDataPolicy, "missing_data_policy"
        ),
        sizing_mode=_as_enum(params["sizing_mode"], SizingMode, "sizing_mode"),
        cash_policy_on_gate_only=str(params["cash_policy_on_gate_only"]),
    )
