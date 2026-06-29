"""Scoring helpers for the bottom-up ROC research slice."""

from __future__ import annotations

import pandas as pd

from .ranking import apply_deterministic_tie_break


class ScoringNotImplementedError(NotImplementedError):
    """Raised when requested scoring variant is not implemented in skeleton."""


def build_roc_scores(
    bars: pd.DataFrame,
    *,
    as_of_date: str,
    lookback_bars: int = 60,
    price_column: str = "close",
    session_timezone: str = "America/New_York",
) -> pd.DataFrame:
    """Compute simple cross-sectional ROC scores on daily bars.

    Uses the last bar on or before ``as_of_date`` and compares against the bar
    ``lookback_bars`` sessions earlier within each symbol series.
    """

    required = {"timestamp", "symbol", price_column}
    missing = sorted(required - set(bars.columns))
    if missing:
        raise ValueError(f"bars missing required columns: {', '.join(missing)}")
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be > 0")

    frame = bars[["timestamp", "symbol", price_column]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"]).sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    as_of_day = pd.Timestamp(as_of_date).date()
    frame["session_date"] = frame["timestamp"].dt.tz_convert(session_timezone).dt.date
    frame = frame[frame["session_date"] <= as_of_day].copy()
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "close", f"roc{lookback_bars}", "score", "bars_available"])

    frame["bars_available"] = frame.groupby("symbol", sort=False).cumcount() + 1
    frame[f"roc{lookback_bars}"] = (
        frame.groupby("symbol", sort=False)[price_column].transform(lambda s: (s / s.shift(lookback_bars)) - 1.0)
    )

    latest = (
        frame.groupby("symbol", as_index=False, sort=False)
        .tail(1)
        .reset_index(drop=True)
    )
    latest = latest[latest[f"roc{lookback_bars}"].notna()].copy()
    if latest.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "close", f"roc{lookback_bars}", "score", "bars_available"])

    latest = latest.rename(columns={price_column: "close", f"roc{lookback_bars}": f"roc{lookback_bars}"})
    latest["score"] = latest[f"roc{lookback_bars}"]
    out = latest[["symbol", "timestamp", "close", f"roc{lookback_bars}", "score", "bars_available"]].copy()
    return apply_deterministic_tie_break(out)


def build_monthly_scores(
    bars: pd.DataFrame,
    *,
    windows_months: list[int],
    score_type: str,
) -> pd.DataFrame:
    """Build placeholder score frame.

    TODO: implement monthly return windowing using month boundaries.
    """

    if "symbol" not in bars.columns:
        raise RuntimeError(
            "ndx_momentum_rotation requires multi-symbol bars with 'symbol' column"
        )
    if bars["symbol"].nunique() < 2:
        raise RuntimeError(
            "ndx_momentum_rotation requires cross-sectional bars with >=2 symbols"
        )

    if score_type not in {"sum_returns", "weighted", "twelve_only"}:
        raise ValueError(f"unsupported score_type: {score_type!r}")

    symbols = sorted(set(bars["symbol"].astype(str)))
    frame = pd.DataFrame({"symbol": symbols, "score": 0.0})
    for window in windows_months:
        frame[f"ret_{window}m"] = 0.0
    return apply_deterministic_tie_break(frame)
