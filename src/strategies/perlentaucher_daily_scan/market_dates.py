"""Daily date helpers for Perlentaucher marketdata inputs."""

from __future__ import annotations

import pandas as pd


def market_date_series(
    ts: pd.Series,
    *,
    session_timezone: str,
    error_prefix: str,
) -> pd.Series:
    """Return stable market dates for D1 bars across supported input shapes.

    marketdata-stream daily endpoints encode trading days as midnight timestamps.
    Those rows are date-based and must stay on their calendar day instead of
    being shifted backwards by a timezone conversion.
    """

    dt = pd.to_datetime(ts, errors="coerce")
    if dt.isna().any():
        raise ValueError(f"{error_prefix} contain invalid timestamps")

    if dt.dt.tz is None:
        return dt.dt.date

    dt_utc = dt.dt.tz_convert("UTC")
    is_utc_midnight = (
        (dt_utc.dt.hour == 0)
        & (dt_utc.dt.minute == 0)
        & (dt_utc.dt.second == 0)
        & (dt_utc.dt.microsecond == 0)
        & (dt_utc.dt.nanosecond == 0)
    )
    if bool(is_utc_midnight.all()):
        return dt_utc.dt.date

    return dt_utc.dt.tz_convert(session_timezone).dt.date


__all__ = ["market_date_series"]
