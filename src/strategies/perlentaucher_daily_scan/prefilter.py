"""Pure daily prefilter logic for perlentaucher_daily_scan."""

from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd

from .debug_hooks import debug_stage_enabled
from .market_dates import market_date_series


REQUIRED_COLUMNS = {"symbol", "timestamp", "low", "close", "volume"}


def _as_market_date_series(ts: pd.Series, session_timezone: str) -> pd.Series:
    return market_date_series(
        ts,
        session_timezone=session_timezone,
        error_prefix="prefilter bars",
    )


def _as_date(value: str | date) -> date:
    return pd.Timestamp(value).date()


def build_volume_prefilter_metrics(
    daily_bars: pd.DataFrame,
    *,
    as_of_date: str | date,
    session_timezone: str = "America/New_York",
    sma_window: int = 50,
    recent_days: int = 6,
    recent_low_window: int = 7,
    min_price: float = 2.5,
    max_price: float = 15.0,
    min_avg_volume_50: float = 100_000.0,
    volume_ratio_threshold: float = 2.5,
) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(daily_bars.columns))
    if missing:
        raise ValueError(
            f"perlentaucher_daily_scan prefilter missing required columns: {', '.join(missing)}"
        )

    as_of = _as_date(as_of_date)
    df = daily_bars.copy().reset_index(drop=True)
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["session_date"] = _as_market_date_series(df["timestamp"], session_timezone)
    df = df[df["session_date"] <= as_of].sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    rows: list[dict] = []
    prior_cutoff = as_of - pd.Timedelta(days=6)

    for symbol, sym_df in df.groupby("symbol", sort=True):
        sym_df = sym_df.sort_values("timestamp").reset_index(drop=True)
        if sym_df.empty:
            continue

        latest = sym_df.iloc[-1]
        latest_session_date = pd.Timestamp(latest["session_date"]).date()
        has_current_bar = latest_session_date == as_of
        target_close = float(latest["close"])
        bars_available = int(len(sym_df))
        sma_value = float(sym_df["close"].rolling(sma_window).mean().iloc[-1]) if bars_available >= sma_window else float("nan")
        above_sma = bool(pd.notna(sma_value) and target_close > sma_value)
        price_in_range = bool(min_price < target_close < max_price)

        recent_window_df = sym_df.tail(recent_low_window)
        last_6_df = sym_df.tail(recent_days)
        prior_50_df = sym_df[sym_df["session_date"] <= prior_cutoff].tail(50)

        has_recent_window = len(last_6_df) == recent_days
        has_prior_window = len(prior_50_df) == 50

        recent_max_low = float(recent_window_df["low"].max()) if not recent_window_df.empty else float("nan")
        low_below_close_ok = bool(pd.notna(recent_max_low) and recent_max_low < target_close)

        avg_volume_recent = float(last_6_df["volume"].mean()) if has_recent_window else float("nan")
        avg_volume_prior = float(prior_50_df["volume"].mean()) if has_prior_window else float("nan")
        volume_ratio = (
            float(avg_volume_recent / avg_volume_prior)
            if pd.notna(avg_volume_recent) and pd.notna(avg_volume_prior) and avg_volume_prior != 0
            else float("nan")
        )
        liquidity_ok = bool(pd.notna(avg_volume_prior) and avg_volume_prior > min_avg_volume_50)
        volume_expansion_ok = bool(
            pd.notna(volume_ratio) and avg_volume_recent >= volume_ratio_threshold * avg_volume_prior
        )

        eligible = bool(
            has_current_bar
            and price_in_range
            and above_sma
            and has_recent_window
            and has_prior_window
            and low_below_close_ok
            and liquidity_ok
        )
        if debug_stage_enabled("prefilter", symbol=symbol, as_of_date=as_of.isoformat()):
            breakpoint()

        rows.append(
            {
                "symbol": symbol,
                "as_of_date": as_of.isoformat(),
                "latest_session_date": latest_session_date.isoformat(),
                "has_current_bar": has_current_bar,
                "bars_available": bars_available,
                "target_close": target_close,
                "sma_value": sma_value,
                "above_sma": above_sma,
                "recent_max_low": recent_max_low,
                "avg_volume_recent": avg_volume_recent,
                "avg_volume_prior": avg_volume_prior,
                "volume_ratio": volume_ratio,
                "price_in_range": price_in_range,
                "has_recent_window": has_recent_window,
                "has_prior_window": has_prior_window,
                "liquidity_ok": liquidity_ok,
                "volume_expansion_ok": volume_expansion_ok,
                "low_below_close_ok": low_below_close_ok,
                "eligible": eligible,
            }
        )

    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


def select_volume_prefilter_candidates(metrics: pd.DataFrame) -> pd.DataFrame:
    if "eligible" not in metrics.columns:
        raise ValueError("prefilter metrics missing required column: eligible")
    return metrics.loc[metrics["eligible"]].copy().sort_values("symbol").reset_index(drop=True)
