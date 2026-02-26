from __future__ import annotations

from typing import Any

import pandas as pd


def session_key_for(
    session_filter: Any,
    ts: pd.Timestamp,
    session_tz: str,
    session_idx: int,
) -> tuple:
    try:
        return session_filter.get_session_key(ts, session_tz)
    except AttributeError:
        session_start = session_filter.get_session_start(ts, session_tz)
        return (session_idx, session_start)


def compute_netting_open_until(
    *,
    validity_policy: str,
    validity_minutes: int,
    validity_bars: int,
    session_filter: Any,
    ts: pd.Timestamp,
    session_tz: str,
) -> pd.Timestamp | None:
    if validity_policy == "session_end":
        return session_filter.get_session_end(ts, session_tz)
    if validity_policy == "fixed_bars":
        return ts + pd.Timedelta(minutes=5 * int(validity_bars))
    if validity_policy == "fixed_minutes":
        netting_open_until = ts + pd.Timedelta(minutes=validity_minutes)
        session_end = session_filter.get_session_end(ts, session_tz)
        if session_end and netting_open_until > session_end:
            return session_end
        return netting_open_until
    return session_filter.get_session_end(ts, session_tz)
