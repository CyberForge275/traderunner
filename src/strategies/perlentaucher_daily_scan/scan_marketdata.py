"""Marketdata fetch helpers for perlentaucher daily scans."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import requests

from .debug_hooks import debug_stage_enabled
from .market_dates import market_date_series


EXPORT_MERGED_ENDPOINT = "/daily/v2/export_merged"
REFRESH_MERGED_ENDPOINT = "/daily/mysql/export_merged"
DEFAULT_SESSION_TIMEZONE = "America/New_York"


def _market_today(session_timezone: str) -> date:
    return pd.Timestamp.now(tz=session_timezone).date()


def _coverage_target_date(
    valid_to: str,
    *,
    session_timezone: str = DEFAULT_SESSION_TIMEZONE,
) -> date:
    requested_end = pd.Timestamp(valid_to).date()
    today_market = _market_today(session_timezone)
    if requested_end < today_market:
        return requested_end
    previous_business_days = pd.bdate_range(end=pd.Timestamp(today_market), periods=2)
    return previous_business_days[0].date()


def _coverage_floor_date(
    valid_from: str,
    *,
    session_timezone: str = DEFAULT_SESSION_TIMEZONE,
) -> date:
    del session_timezone
    first_business_day = pd.bdate_range(start=pd.Timestamp(valid_from), periods=1)
    return first_business_day[0].date()


def _request_export_meta(
    *,
    base_url: str,
    endpoint: str,
    payload: dict,
) -> dict:
    response = requests.post(
        f"{base_url.rstrip('/')}{endpoint}",
        json=payload,
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def _read_export_frame(meta: dict) -> pd.DataFrame:
    merged_path = Path(meta["merged_parquet_path"])
    if not merged_path.exists():
        raise FileNotFoundError(f"marketdata export parquet not found: {merged_path}")
    return pd.read_parquet(merged_path)


def _frame_session_bounds(raw_df: pd.DataFrame) -> tuple[date | None, date | None]:
    if raw_df.empty:
        return None, None
    time_col = "date" if "date" in raw_df.columns else "timestamp"
    session_dates = market_date_series(
        raw_df[time_col],
        session_timezone=DEFAULT_SESSION_TIMEZONE,
        error_prefix="perlentaucher scan marketdata export",
    )
    if session_dates.empty:
        return None, None
    return min(session_dates), max(session_dates)


def _ensure_required_end_date_coverage(
    *,
    session_max: date | None,
    coverage_target_to: str,
    requested_valid_to: str,
    source_endpoint: str,
    coverage_refresh_triggered: bool,
) -> None:
    target_date = pd.Timestamp(coverage_target_to).date()
    if session_max is not None and session_max >= target_date:
        return
    raise RuntimeError(
        "perlentaucher_daily_scan marketdata coverage check failed after refresh: "
        f"requested_valid_to={requested_valid_to} "
        f"coverage_target_to={coverage_target_to} "
        f"data_session_max={None if session_max is None else session_max.isoformat()} "
        f"source_endpoint={source_endpoint} "
        f"coverage_refresh_triggered={coverage_refresh_triggered}"
    )


def _ensure_required_start_date_coverage(
    *,
    session_min: date | None,
    coverage_target_from: str,
    requested_valid_from: str,
    source_endpoint: str,
    coverage_refresh_triggered: bool,
) -> None:
    target_date = pd.Timestamp(coverage_target_from).date()
    if session_min is not None and session_min <= target_date:
        return
    raise RuntimeError(
        "perlentaucher_daily_scan marketdata history coverage check failed after refresh: "
        f"requested_valid_from={requested_valid_from} "
        f"coverage_target_from={coverage_target_from} "
        f"data_session_min={None if session_min is None else session_min.isoformat()} "
        f"source_endpoint={source_endpoint} "
        f"coverage_refresh_triggered={coverage_refresh_triggered}"
    )


def fetch_scan_marketdata(
    *,
    base_url: str,
    request_payload: dict,
    requested_valid_to: str,
) -> tuple[pd.DataFrame, dict]:
    source_endpoint = EXPORT_MERGED_ENDPOINT
    coverage_target_from = _coverage_floor_date(str(request_payload["valid_from"])).isoformat()
    coverage_target_to = _coverage_target_date(requested_valid_to).isoformat()

    meta = _request_export_meta(
        base_url=base_url,
        endpoint=EXPORT_MERGED_ENDPOINT,
        payload=request_payload,
    )
    raw_df = _read_export_frame(meta)
    session_min, session_max = _frame_session_bounds(raw_df)

    coverage_refresh_triggered = False
    if session_max is None or session_max < pd.Timestamp(coverage_target_to).date():
        refresh_meta = _request_export_meta(
            base_url=base_url,
            endpoint=REFRESH_MERGED_ENDPOINT,
            payload={
                "universe": "US",
                "symbol": "ALL",
                "valid_from": request_payload["valid_from"],
                "valid_to": request_payload["valid_to"],
            },
        )
        refresh_df = _read_export_frame(refresh_meta)
        refresh_min, refresh_max = _frame_session_bounds(refresh_df)
        coverage_refresh_triggered = True
        if refresh_max is not None and (session_max is None or refresh_max >= session_max):
            meta = refresh_meta
            raw_df = refresh_df
            session_min, session_max = refresh_min, refresh_max
            source_endpoint = REFRESH_MERGED_ENDPOINT

    if debug_stage_enabled("fetch_data", as_of_date=requested_valid_to):
        breakpoint()
    meta = {
        **meta,
        "source_endpoint": source_endpoint,
        "coverage_refresh_triggered": coverage_refresh_triggered,
        "coverage_target_from": coverage_target_from,
        "coverage_target_to": coverage_target_to,
        "data_session_min": None if session_min is None else session_min.isoformat(),
        "data_session_max": None if session_max is None else session_max.isoformat(),
    }
    if debug_stage_enabled("coverage", as_of_date=requested_valid_to):
        breakpoint()
    _ensure_required_start_date_coverage(
        session_min=session_min,
        coverage_target_from=coverage_target_from,
        requested_valid_from=str(request_payload["valid_from"]),
        source_endpoint=source_endpoint,
        coverage_refresh_triggered=coverage_refresh_triggered,
    )
    _ensure_required_end_date_coverage(
        session_max=session_max,
        coverage_target_to=coverage_target_to,
        requested_valid_to=requested_valid_to,
        source_endpoint=source_endpoint,
        coverage_refresh_triggered=coverage_refresh_triggered,
    )
    return raw_df, meta


__all__ = [
    "DEFAULT_SESSION_TIMEZONE",
    "EXPORT_MERGED_ENDPOINT",
    "REFRESH_MERGED_ENDPOINT",
    "fetch_scan_marketdata",
]
