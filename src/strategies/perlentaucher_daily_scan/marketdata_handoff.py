"""Handoff payload builder for external Perlentaucher marketdata implementation."""

from __future__ import annotations

from .feature_contract import FEATURE_COLUMNS, IDENTIFIER_COLUMNS
from .marketdata_request import build_stock_universe_request


REQUIRED_OHLCV_COLUMNS = (
    "symbol",
    "trading_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

REQUIRED_FEATURE_COLUMNS = (
    *IDENTIFIER_COLUMNS,
    *FEATURE_COLUMNS,
)


def build_marketdata_handoff_payload(
    *,
    date_from: str,
    date_to: str,
    params: dict,
) -> dict:
    req = build_stock_universe_request(
        date_from=date_from,
        date_to=date_to,
        params=params,
    )
    return {
        "request": {
            "market": req.market,
            "asset_class": req.asset_class,
            "symbol_mode": "ALL",
            "date_from": req.date_from.isoformat(),
            "date_to": req.date_to.isoformat(),
            "lookback_days": req.lookback_days,
            "fetch_calendar_days": req.fetch_calendar_days,
        },
        "input_contract": {
            "required_ohlcv_columns": list(REQUIRED_OHLCV_COLUMNS),
            "price_source": "close",
            "volume_source": "volume",
            "market_timezone": "America/New_York",
        },
        "output_contract": {
            "required_feature_columns": list(REQUIRED_FEATURE_COLUMNS),
            "row_key": ["symbol", "as_of_date"],
        },
        "calculation_parameters": {
            "trend_short_bars": 7,
            "trend_mid_bars": 13,
            "trend_long_bars": 100,
            "trend_long_offset_bars": 7,
        },
    }


__all__ = [
    "REQUIRED_OHLCV_COLUMNS",
    "REQUIRED_FEATURE_COLUMNS",
    "build_marketdata_handoff_payload",
]
