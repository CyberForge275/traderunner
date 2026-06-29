"""Prefilter candidate scans across a requested trading-date range."""

from __future__ import annotations

import pandas as pd

from .daily_pipeline import normalize_daily_ohlcv_frame, select_prefilter_candidate_symbols
from .scan_dates import coerce_scan_date, scan_session_dates


def scan_candidate_dates(
    raw_daily_df: pd.DataFrame,
    *,
    valid_from: str | pd.Timestamp,
    valid_to: str | pd.Timestamp,
    session_timezone: str = "America/New_York",
) -> pd.DataFrame:
    start_date = coerce_scan_date(valid_from)
    end_date = coerce_scan_date(valid_to)

    daily_df = normalize_daily_ohlcv_frame(raw_daily_df)
    scan_dates = scan_session_dates(
        daily_df["timestamp"],
        valid_from=start_date,
        valid_to=end_date,
        session_timezone=session_timezone,
        error_prefix="candidate scan bars",
    )

    rows: list[dict] = []
    for as_of_date in scan_dates:
        _, candidate_symbols = select_prefilter_candidate_symbols(
            daily_df,
            as_of_date=as_of_date.isoformat(),
        )
        rows.append(
            {
                "as_of_date": as_of_date.isoformat(),
                "symbol_count": len(candidate_symbols),
                "symbols": candidate_symbols,
                "symbols_csv": ",".join(candidate_symbols),
            }
        )

    return pd.DataFrame(
        rows,
        columns=["as_of_date", "symbol_count", "symbols", "symbols_csv"],
    )


__all__ = ["scan_candidate_dates"]
