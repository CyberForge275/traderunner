"""Marketdata request builder for perlentaucher_daily_scan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math

from .config import DEFAULT_MIN_HISTORY_DAYS, build_perlentaucher_daily_scan_config

DEFAULT_MIN_FETCH_CALENDAR_DAYS = 175
FETCH_HISTORY_MULTIPLIER = 1.65


@dataclass(frozen=True)
class StockUniverseRequest:
    market: str
    asset_class: str
    date_from: date
    date_to: date
    lookback_days: int
    fetch_calendar_days: int


def _as_date(value: str | date) -> date:
    return date.fromisoformat(str(value)[:10])


def build_stock_universe_request(
    *,
    date_from: str | date,
    date_to: str | date,
    params: dict,
) -> StockUniverseRequest:
    cfg = build_perlentaucher_daily_scan_config(
        {
            **params,
            "enabled": params.get("enabled", True),
            "timeframe_minutes": params.get("timeframe_minutes", 1440),
            "match_mode": params.get("match_mode", "price_vol"),
            "use_volume_prefilter": params.get("use_volume_prefilter", True),
            "reference_set": params.get("reference_set", "default"),
            "max_candidates": params.get("max_candidates", 25),
        }
    )

    requested_from = _as_date(date_from)
    requested_to = _as_date(date_to)
    if requested_from > requested_to:
        raise ValueError("date_from must be <= date_to")

    fetch_calendar_days = max(
        DEFAULT_MIN_FETCH_CALENDAR_DAYS,
        int(math.ceil(cfg.min_history_days * FETCH_HISTORY_MULTIPLIER)),
    )
    minimum_from = requested_to - timedelta(days=fetch_calendar_days - 1)
    resolved_from = min(requested_from, minimum_from)

    return StockUniverseRequest(
        market="US",
        asset_class="stock",
        date_from=resolved_from,
        date_to=requested_to,
        lookback_days=cfg.min_history_days,
        fetch_calendar_days=fetch_calendar_days,
    )


__all__ = [
    "DEFAULT_MIN_HISTORY_DAYS",
    "DEFAULT_MIN_FETCH_CALENDAR_DAYS",
    "StockUniverseRequest",
    "build_stock_universe_request",
]
