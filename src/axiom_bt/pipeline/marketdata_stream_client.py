from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from core.settings.runtime_config import (
    RuntimeConfigError,
    get_marketdata_data_root,
    get_runtime_config,
)


def _to_date(x: Any) -> dt.date:
    if isinstance(x, dt.date) and not isinstance(x, dt.datetime):
        return x
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, str):
        return dt.date.fromisoformat(x[:10])
    raise TypeError(f"Unsupported date type: {type(x)}")


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass(frozen=True)
class EnsureBarsRequest:
    symbol: str
    timeframe_minutes: int
    start_date: dt.date
    end_date: dt.date
    session_timezone: str = "America/New_York"
    session_mode: str = "rth"
    session_filter: Optional[list[str]] = None
    data_root: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "symbol": self.symbol,
            "timeframe_minutes": int(self.timeframe_minutes),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "session_timezone": self.session_timezone,
            "session_mode": self.session_mode,
        }
        if self.session_filter is not None:
            payload["session_filter"] = list(self.session_filter)
        if self.data_root:
            payload["data_root"] = self.data_root
        return payload


class MarketdataStreamClient:
    """
    Optional helper: UI/CLI can ask marketdata-stream to ensure/backfill range.
    Pipeline remains SSOT.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_sec: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        resolved_base_url = base_url
        if not resolved_base_url:
            try:
                resolved_base_url = get_runtime_config().services.marketdata_stream_url
            except RuntimeConfigError:
                resolved_base_url = os.getenv("MARKETDATA_STREAM_URL")
        self.base_url = (resolved_base_url or "").rstrip("/")
        self.timeout_sec = int(timeout_sec or os.getenv("MARKETDATA_STREAM_TIMEOUT_SEC") or "180")
        if enabled is None:
            self.enabled = _env_bool("PIPELINE_AUTO_ENSURE_BARS", False)
        else:
            self.enabled = enabled

    def is_configured(self) -> bool:
        return bool(self.base_url) and self.enabled

    def ensure_bars(self, req: EnsureBarsRequest) -> Dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "skipped": True, "reason": "MARKETDATA_STREAM_URL not set or disabled"}

        url = f"{self.base_url}/ensure_timeframe_bars"
        r = requests.post(url, json=req.to_json(), timeout=self.timeout_sec)
        try:
            data = r.json()
        except Exception:
            data = {"ok": False, "status_code": r.status_code, "text": r.text}

        status = str(data.get("status", "")).lower()
        ok = status in {"ok", "backfilled"} or bool(data.get("ok", False))
        if r.status_code >= 400 or not ok:
            raise RuntimeError(f"marketdata-stream ensure_bars failed: status={r.status_code} body={data}")
        return data


def build_ensure_request_for_pipeline(
    symbol: str,
    timeframe_minutes: int,
    start_date: Any,
    end_date: Any,
    lookback_candles: int = 0,
    session_timezone: str = "America/New_York",
    session_mode: str = "rth",
    session_filter: Optional[list[str]] = None,
    data_root: Optional[str] = None,
) -> EnsureBarsRequest:
    """
    Pipeline may add internal lookback days. Use a small buffer for ensure/backfill.
    """
    s = _to_date(start_date)
    e = _to_date(end_date)
    bars_per_day = 78 if (session_mode or "").lower() == "rth" and int(timeframe_minutes) == 5 else 200
    extra_days = 2
    if lookback_candles and lookback_candles > 0:
        extra_days += max(1, int((lookback_candles + bars_per_day - 1) / bars_per_day))
    ensure_start = s - dt.timedelta(days=extra_days)
    return EnsureBarsRequest(
        symbol=symbol,
        timeframe_minutes=int(timeframe_minutes),
        start_date=ensure_start,
        end_date=e,
        session_timezone=session_timezone,
        session_mode=session_mode,
        session_filter=session_filter,
        data_root=data_root or str(get_marketdata_data_root()),
    )
