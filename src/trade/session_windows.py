from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import List

import pandas as pd


@dataclass(frozen=True)
class SessionWindow:
    start: time
    end: time


def parse_session_filter(session_filter: List[str]) -> List[SessionWindow]:
    if not session_filter:
        raise ValueError("session_filter must be a non-empty list of 'HH:MM-HH:MM' strings")
    windows: List[SessionWindow] = []
    for raw in session_filter:
        s = raw.strip()
        if "-" not in s:
            raise ValueError(f"invalid session window: '{raw}' (expected HH:MM-HH:MM)")
        start_str, end_str = s.split("-", 1)
        try:
            h1, m1 = map(int, start_str.split(":"))
            h2, m2 = map(int, end_str.split(":"))
        except ValueError as exc:
            raise ValueError(f"invalid session window: '{raw}' (expected HH:MM-HH:MM)") from exc
        start = time(h1, m1)
        end = time(h2, m2)
        if end <= start:
            raise ValueError(f"invalid session window: '{raw}' (end must be after start)")
        windows.append(SessionWindow(start=start, end=end))
    return windows


def session_end_for_day(
    ts_utc: pd.Timestamp, session_filter: List[str], session_timezone: str
) -> pd.Timestamp:
    if not session_timezone:
        raise ValueError("session_timezone must be provided")
    windows = parse_session_filter(session_filter)
    if ts_utc.tz is None:
        ts_utc = ts_utc.tz_localize("UTC")
    ts_local = ts_utc.tz_convert(session_timezone)
    end_time = max(w.end for w in windows)
    session_end_local = ts_local.replace(
        hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0
    )
    return session_end_local.tz_convert("UTC")


def session_window_end_for_ts(
    ts_utc: pd.Timestamp, session_filter: List[str], session_timezone: str
) -> pd.Timestamp:
    if not session_timezone:
        raise ValueError("session_timezone must be provided")
    windows = parse_session_filter(session_filter)
    if ts_utc.tz is None:
        ts_utc = ts_utc.tz_localize("UTC")
    ts_local = ts_utc.tz_convert(session_timezone)
    t = ts_local.timetz().replace(tzinfo=None)
    for w in windows:
        if w.start <= t <= w.end:
            window_end_local = ts_local.replace(
                hour=w.end.hour, minute=w.end.minute, second=0, microsecond=0
            )
            return window_end_local.tz_convert("UTC")
    raise ValueError("timestamp not within any session window")
