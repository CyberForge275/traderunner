"""Pattern detection helpers for harami_break."""

from __future__ import annotations

import pandas as pd

from trade.session_windows import parse_session_filter
from .rules import eval_vectorized


def detect_inside_pattern(df: pd.DataFrame, *, definition_mode: str, strict: bool) -> pd.Series:
    """Return the boolean InsideBar mask for a prepared OHLC dataframe.

    Purpose
    -------
    This function is the thin adapter between raw dataframe input and the
    vectorized rule engine in ``rules.py``. It does not mutate input and does
    not add columns; it only returns a mask aligned to ``df.index``.

    Inputs
    ------
    df:
        DataFrame containing at least OHLC columns required by the selected
        ``definition_mode`` (typically ``open/high/low/close``).
    definition_mode:
        Named rule variant (SSOT-defined), e.g. range-based or body-based IB
        definitions.
    strict:
        Rule strictness switch forwarded 1:1 to the rule engine. This controls
        inclusive vs stricter comparisons inside the pattern check.

    Output
    ------
    pd.Series[bool]:
        ``True`` where the current bar is considered an InsideBar relative to
        its mother bar (previous candle), ``False`` otherwise.
    """
    return eval_vectorized(df, definition_mode, strict)


def enrich_inside_pattern_frame(
    df: pd.DataFrame,
    *,
    definition_mode: str,
    strict: bool,
    min_mother_body_fraction: float,
    max_mother_body_fraction: float,
    session_windows: list[str] | None = None,
    session_timezone: str | None = None,
) -> pd.DataFrame:
    """Enrich bars with mother/inside pattern diagnostics used downstream.

    Purpose
    -------
    Build an analysis dataframe that contains pattern context columns required
    by the next strategy stages (arming/window/trigger evaluation). The
    function is intentionally deterministic and index-aligned: each output row
    corresponds to the same input bar.

    Added Columns
    -------------
    prev_high/prev_low/prev_open/prev_close:
        Previous bar OHLC values (mother-candidate context).
    mother_bar_ts:
        Timestamp of the previous bar (mother-candidate timestamp).
    is_inside_bar:
        Boolean mask for InsideBar rows according to rule mode + strictness.
    is_motherbar:
        Boolean mask for bars that are immediately followed by an InsideBar.
    armed:
        Boolean pre-condition flag; either equals ``is_inside_bar`` (no session
        filtering) or ``is_inside_bar AND in_session_window`` when session
        constraints are provided.
    mother_bar_high/mother_bar_low:
        Mother levels materialized only for InsideBar rows.

    Session Handling
    ----------------
    If ``session_windows`` and ``session_timezone`` are provided, timestamps are
    converted to local session time and only bars inside the configured windows
    are marked as ``armed``. If either is missing, arming falls back to raw
    pattern presence (no time gate).

    Notes
    -----
    - This function does not place orders and does not compute fills.
    - It is a feature-engineering step for later strategy state machine logic.
    """
    out = df.copy()
    out["prev_high"] = out["high"].shift(1)
    out["prev_low"] = out["low"].shift(1)
    out["prev_open"] = out["open"].shift(1)
    out["prev_close"] = out["close"].shift(1)
    mother_range = (out["prev_high"] - out["prev_low"]).abs()
    mother_body = (out["prev_close"] - out["prev_open"]).abs()
    out["mother_body_fraction"] = (mother_body / mother_range.where(mother_range > 0)).fillna(0.0)
    out["mother_body_ok"] = (
        (out["mother_body_fraction"] >= float(min_mother_body_fraction))
        & (out["mother_body_fraction"] <= float(max_mother_body_fraction))
    )
    if "timestamp" in out.columns:
        out["mother_bar_ts"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce").shift(1)
    else:
        out["mother_bar_ts"] = pd.NaT

    inside_mask = detect_inside_pattern(out, definition_mode=definition_mode, strict=strict).fillna(False)
    filtered_inside_mask = inside_mask & out["mother_body_ok"].fillna(False).astype(bool)
    out["is_inside_bar"] = inside_mask
    out["is_motherbar"] = filtered_inside_mask.shift(-1, fill_value=False).astype(bool)
    if session_windows and session_timezone and "timestamp" in out.columns:
        windows = parse_session_filter(session_windows)
        ts_local = pd.to_datetime(out["timestamp"], utc=True, errors="coerce").dt.tz_convert(session_timezone)
        local_t = ts_local.dt.time
        in_window = pd.Series(False, index=out.index)
        for w in windows:
            in_window |= (local_t >= w.start) & (local_t <= w.end)
        out["armed"] = (filtered_inside_mask & in_window.fillna(False)).astype(bool)
    else:
        out["armed"] = filtered_inside_mask.astype(bool)
    out["mother_bar_high"] = out["prev_high"].where(filtered_inside_mask)
    out["mother_bar_low"] = out["prev_low"].where(filtered_inside_mask)
    return out
