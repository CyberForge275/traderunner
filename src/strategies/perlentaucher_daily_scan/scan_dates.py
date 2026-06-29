"""Shared trading-date helpers for Perlentaucher scans."""

from __future__ import annotations

from datetime import date

import pandas as pd

from .market_dates import market_date_series


def coerce_scan_date(value: str | date) -> date:
    return pd.Timestamp(value).date()


def scan_session_dates(
    timestamp_series: pd.Series,
    *,
    valid_from: str | date,
    valid_to: str | date,
    session_timezone: str,
    error_prefix: str,
) -> list[date]:
    start_date = coerce_scan_date(valid_from)
    end_date = coerce_scan_date(valid_to)
    if start_date > end_date:
        raise ValueError("valid_from must be <= valid_to")

    session_dates = market_date_series(
        timestamp_series,
        session_timezone=session_timezone,
        error_prefix=error_prefix,
    )
    return sorted({day for day in session_dates if start_date <= day <= end_date})


__all__ = ["coerce_scan_date", "scan_session_dates"]
