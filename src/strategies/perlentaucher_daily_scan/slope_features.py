"""Performance-aware slope feature builders for perlentaucher_daily_scan."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .debug_hooks import debug_stage_enabled
from .feature_contract import FEATURE_COLUMNS


def _as_date(value: str) -> str:
    return pd.Timestamp(value).date().isoformat()


def compute_lr_slope_series(values: pd.Series, window: int) -> pd.Series:
    if window <= 1:
        raise ValueError("window must be > 1")

    y = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float, copy=False)
    out = np.full(len(y), np.nan, dtype=float)
    if len(y) < window:
        return pd.Series(out, index=values.index, dtype=float)

    x = np.arange(window, dtype=float)
    sum_x = x.sum()
    sum_x2 = np.square(x).sum()
    denom = window * sum_x2 - sum_x * sum_x

    for end in range(window - 1, len(y)):
        window_y = y[end - window + 1 : end + 1]
        if np.isnan(window_y).any():
            continue
        sum_y = window_y.sum()
        sum_xy = np.dot(x, window_y)
        out[end] = (window * sum_xy - sum_x * sum_y) / denom

    return pd.Series(out, index=values.index, dtype=float)


def build_slope_feature_history_frame(
    daily_df: pd.DataFrame,
    *,
    as_of_date: str,
    short_window: int = 7,
    mid_window: int = 13,
    long_window: int = 100,
    long_offset: int = 7,
) -> pd.DataFrame:
    target_date = _as_date(as_of_date)
    if daily_df.empty:
        return pd.DataFrame(columns=["symbol", "as_of_date", *FEATURE_COLUMNS])

    frames: list[pd.DataFrame] = []
    grouped = daily_df.sort_values(["symbol", "timestamp"]).groupby("symbol", sort=True)
    for symbol, sym_df in grouped:
        sym_df = sym_df.copy().reset_index(drop=True)
        sym_df["as_of_date"] = pd.to_datetime(sym_df["timestamp"], utc=True).dt.date.astype(str)

        sym_df["price_short"] = compute_lr_slope_series(sym_df["close"], short_window)
        sym_df["price_mid"] = compute_lr_slope_series(sym_df["close"], mid_window)
        sym_df["price_long"] = compute_lr_slope_series(sym_df["close"], long_window)
        sym_df["vol_short"] = compute_lr_slope_series(sym_df["volume"], short_window)
        sym_df["vol_mid"] = compute_lr_slope_series(sym_df["volume"], mid_window)
        sym_df["vol_long"] = compute_lr_slope_series(sym_df["volume"], long_window)

        sym_df["price_l_long"] = sym_df["price_long"].shift(long_offset)
        sym_df["vol_l_long"] = sym_df["vol_long"].shift(long_offset)

        eligible = sym_df.loc[sym_df["as_of_date"] <= target_date].copy()
        if eligible.empty:
            continue
        eligible = eligible.dropna(
            subset=[
                "price_short",
                "price_mid",
                "price_l_long",
                "vol_short",
                "vol_mid",
                "vol_l_long",
            ]
        )
        if debug_stage_enabled("slope", symbol=str(symbol), as_of_date=target_date):
            breakpoint()
        if eligible.empty:
            continue

        frames.append(
            eligible.loc[
                :,
                [
                    "symbol",
                    "as_of_date",
                    "price_short",
                    "price_mid",
                    "price_l_long",
                    "vol_short",
                    "vol_mid",
                    "vol_l_long",
                ],
            ]
        )

    if not frames:
        return pd.DataFrame(columns=["symbol", "as_of_date", *FEATURE_COLUMNS])

    return pd.concat(frames, ignore_index=True).sort_values("symbol").reset_index(drop=True)


def build_slope_feature_frame(
    daily_df: pd.DataFrame,
    *,
    as_of_date: str,
    short_window: int = 7,
    mid_window: int = 13,
    long_window: int = 100,
    long_offset: int = 7,
) -> pd.DataFrame:
    history = build_slope_feature_history_frame(
        daily_df,
        as_of_date=as_of_date,
        short_window=short_window,
        mid_window=mid_window,
        long_window=long_window,
        long_offset=long_offset,
    )
    if history.empty:
        return history

    latest_date = history["as_of_date"].max()
    latest = history.loc[history["as_of_date"] == latest_date].copy()
    return latest.sort_values("symbol").reset_index(drop=True)


def build_inspection_view(
    candidate_daily_df: pd.DataFrame,
    feature_df: pd.DataFrame,
    *,
    as_of_date: str,
) -> pd.DataFrame:
    target_date = _as_date(as_of_date)
    latest_rows = candidate_daily_df.copy()
    latest_rows["as_of_date"] = pd.to_datetime(latest_rows["timestamp"], utc=True).dt.date.astype(str)
    latest_rows = latest_rows.loc[latest_rows["as_of_date"] <= target_date].copy()
    latest_rows = (
        latest_rows.sort_values(["symbol", "timestamp"])
        .drop_duplicates(subset=["symbol", "as_of_date"], keep="last")
        .sort_values(["symbol", "as_of_date"])
        .drop_duplicates(subset=["symbol"], keep="last")
        .reset_index(drop=True)
    )
    if latest_rows.empty:
        return latest_rows
    out = latest_rows.merge(feature_df, on=["symbol", "as_of_date"], how="inner")
    return out.reset_index(drop=True)
