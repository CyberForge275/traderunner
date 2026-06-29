"""Calendar helpers for monthly rebalance schedule (skeleton)."""

from __future__ import annotations

import pandas as pd


def build_monthly_rebalance_calendar(bars: pd.DataFrame) -> pd.DataFrame:
    """Return skeleton monthly schedule derived from bar timestamps.

    TODO: implement exchange-aware first trading day logic.
    """

    if "timestamp" not in bars.columns:
        raise ValueError("bars must include timestamp column")
    ts = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError("timestamp contains invalid values")

    out = pd.DataFrame({"timestamp": ts})
    out["rebalance_month"] = out["timestamp"].dt.strftime("%Y-%m")
    out["is_month_end_signal"] = False
    out["is_month_start_exec"] = False
    return out
