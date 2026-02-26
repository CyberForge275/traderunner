"""Pattern detection helpers for harami_break."""

from __future__ import annotations

import pandas as pd

from trade.session_windows import parse_session_filter
from .rules import eval_vectorized


def detect_inside_pattern(df: pd.DataFrame, *, definition_mode: str, strict: bool) -> pd.Series:
    """Return inside-pattern mask using the shared definition-mode rules."""
    return eval_vectorized(df, definition_mode, strict)


def enrich_inside_pattern_frame(
    df: pd.DataFrame,
    *,
    definition_mode: str,
    strict: bool,
    session_windows: list[str] | None = None,
    session_timezone: str | None = None,
) -> pd.DataFrame:
    """Extend frame with inside/mother-bar columns for downstream strategy logic."""
    out = df.copy()
    out["prev_high"] = out["high"].shift(1)
    out["prev_low"] = out["low"].shift(1)
    out["prev_open"] = out["open"].shift(1)
    out["prev_close"] = out["close"].shift(1)
    if "timestamp" in out.columns:
        out["mother_bar_ts"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce").shift(1)
    else:
        out["mother_bar_ts"] = pd.NaT

    inside_mask = detect_inside_pattern(out, definition_mode=definition_mode, strict=strict).fillna(False)
    out["is_inside_bar"] = inside_mask
    out["is_motherbar"] = inside_mask.shift(-1, fill_value=False).astype(bool)
    if session_windows and session_timezone and "timestamp" in out.columns:
        windows = parse_session_filter(session_windows)
        ts_local = pd.to_datetime(out["timestamp"], utc=True, errors="coerce").dt.tz_convert(session_timezone)
        local_t = ts_local.dt.time
        in_window = pd.Series(False, index=out.index)
        for w in windows:
            in_window |= (local_t >= w.start) & (local_t <= w.end)
        out["armed"] = (inside_mask & in_window.fillna(False)).astype(bool)
    else:
        out["armed"] = inside_mask.astype(bool)
    out["mother_bar_high"] = out["prev_high"].where(inside_mask)
    out["mother_bar_low"] = out["prev_low"].where(inside_mask)
    return out
