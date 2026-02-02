"""Helpers for adding derived time columns to UI tables."""
from __future__ import annotations

from typing import Iterable
import pandas as pd


def add_ny_time_columns(df: pd.DataFrame, cols: Iterable[str], suffix: str = "_ny") -> pd.DataFrame:
    """Add NY-localized timestamp string columns for the given UTC columns."""
    if df.empty:
        return df
    out = df.copy()
    for col in cols:
        if col in out.columns:
            ts = pd.to_datetime(out[col], errors="coerce", utc=True)
            out[f"{col}{suffix}"] = ts.dt.tz_convert("America/New_York").dt.strftime(
                "%Y-%m-%d %H:%M:%S%z"
            )
    return out


def add_buy_sell_ny_columns(df: pd.DataFrame, entry_col: str, exit_col: str, side_col: str = "side") -> pd.DataFrame:
    """Add buy_ts_ny/sell_ts_ny derived from side + entry/exit timestamps."""
    if df.empty:
        return df

    out = df.copy()
    if side_col not in out.columns:
        return add_ny_time_columns(out, [entry_col, exit_col])

    entry_ts = pd.to_datetime(out.get(entry_col), errors="coerce", utc=True)
    exit_ts = pd.to_datetime(out.get(exit_col), errors="coerce", utc=True)

    side = out[side_col].astype(str).str.upper()
    buy_ts = entry_ts.where(side == "BUY", exit_ts)
    sell_ts = exit_ts.where(side == "BUY", entry_ts)

    out["buy_ts_ny"] = buy_ts.dt.tz_convert("America/New_York").dt.strftime(
        "%Y-%m-%d %H:%M:%S%z"
    )
    out["sell_ts_ny"] = sell_ts.dt.tz_convert("America/New_York").dt.strftime(
        "%Y-%m-%d %H:%M:%S%z"
    )
    out["buy_ts_ny"] = out["buy_ts_ny"].fillna("")
    out["sell_ts_ny"] = out["sell_ts_ny"].fillna("")

    return out
