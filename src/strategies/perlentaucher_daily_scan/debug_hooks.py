"""Env-driven programmatic breakpoint helpers for Spyder debugging."""

from __future__ import annotations

import os


SUPPORTED_DEBUG_STAGES = frozenset(
    {
        "request_window",
        "fetch_request",
        "fetch_data",
        "coverage",
        "normalize",
        "prefilter",
        "candidate_select",
        "sweet_spot_config",
        "sweet_spot_cache",
        "slope",
        "candidate_feature_filter",
        "reference",
        "match",
        "summary",
        "cli_state",
    }
)


def _normalized_stage_tokens() -> set[str]:
    return {
        token.strip().lower()
        for token in os.getenv("PT_DEBUG_STAGES", "").split(",")
        if token.strip()
    }


def _normalized_symbol(symbol: str | None) -> str:
    return str(symbol or "").strip().upper()


def _normalized_date(as_of_date: str | None) -> str:
    return str(as_of_date or "").strip()[:10]


def debug_stage_enabled(
    stage: str,
    *,
    symbol: str | None = None,
    as_of_date: str | None = None,
) -> bool:
    normalized_stage = str(stage).strip().lower()
    configured_stages = _normalized_stage_tokens()
    if not configured_stages:
        return False
    if normalized_stage not in configured_stages and "all" not in configured_stages and "*" not in configured_stages:
        return False

    expected_symbol = _normalized_symbol(os.getenv("PT_DEBUG_SYMBOL"))
    if expected_symbol and symbol is not None and _normalized_symbol(symbol) != expected_symbol:
        return False

    expected_date = _normalized_date(os.getenv("PT_DEBUG_DATE"))
    if expected_date and _normalized_date(as_of_date) != expected_date:
        return False

    return True


__all__ = [
    "SUPPORTED_DEBUG_STAGES",
    "debug_stage_enabled",
]
