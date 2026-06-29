"""Typed configuration contract for perlentaucher_daily_scan skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


DEFAULT_MIN_HISTORY_DAYS = 107


class MatchMode(str, Enum):
    PRICE_VOL = "price_vol"
    ZSCORE = "zscore"


class ReferenceSet(str, Enum):
    DEFAULT = "default"


@dataclass(frozen=True)
class PerlentaucherDailyScanConfig:
    enabled: bool
    timeframe_minutes: int
    match_mode: MatchMode
    use_volume_prefilter: bool
    reference_set: ReferenceSet
    min_history_days: int
    max_candidates: int


def _as_enum(value: Any, enum_cls: type[Enum], field: str) -> Enum:
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = sorted(member.value for member in enum_cls)
        raise ValueError(f"invalid {field}: {value!r} (allowed: {allowed})") from exc


def build_perlentaucher_daily_scan_config(
    params: dict[str, Any],
) -> PerlentaucherDailyScanConfig:
    required = {
        "enabled",
        "timeframe_minutes",
        "match_mode",
        "use_volume_prefilter",
        "reference_set",
        "min_history_days",
        "max_candidates",
    }
    missing = sorted(required - set(params.keys()))
    if missing:
        raise ValueError(
            "perlentaucher_daily_scan missing required config keys: " + ", ".join(missing)
        )

    timeframe_minutes = params["timeframe_minutes"]
    if timeframe_minutes != 1440:
        raise ValueError("timeframe_minutes must be 1440 for perlentaucher_daily_scan")

    max_candidates = params["max_candidates"]
    if not isinstance(max_candidates, int) or max_candidates <= 0:
        raise ValueError("max_candidates must be int > 0")

    min_history_days = params["min_history_days"]
    if not isinstance(min_history_days, int) or min_history_days < DEFAULT_MIN_HISTORY_DAYS:
        raise ValueError(f"min_history_days must be int >= {DEFAULT_MIN_HISTORY_DAYS}")

    return PerlentaucherDailyScanConfig(
        enabled=bool(params["enabled"]),
        timeframe_minutes=timeframe_minutes,
        match_mode=_as_enum(params["match_mode"], MatchMode, "match_mode"),
        use_volume_prefilter=bool(params["use_volume_prefilter"]),
        reference_set=_as_enum(params["reference_set"], ReferenceSet, "reference_set"),
        min_history_days=min_history_days,
        max_candidates=max_candidates,
    )
