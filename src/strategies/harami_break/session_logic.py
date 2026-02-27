"""Session validity logic for harami_break signal lifecycle."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from trade.session_windows import session_window_end_for_ts


def apply_signal_validity(
    df: pd.DataFrame,
    *,
    timeframe_minutes: int,
    session_windows: list[str],
    session_timezone: str,
    order_validity_policy: str,
    order_validity_minutes: int,
    order_validity_bars: int,
) -> pd.DataFrame:
    """Apply validity timestamps for armed setups.

    Rules implemented:
    - `armed_from_ts` starts on the NEXT bar after inside bar (exclusive IB bar).
    - `valid_until_ts` follows `order_validity_policy` only.
    - no breakout-window cap is applied in this step.
    """
    out = df.copy()
    if "timestamp" not in out.columns:
        raise ValueError("timestamp column required for signal validity")
    if "armed" not in out.columns:
        raise ValueError("armed column required for signal validity")

    ts = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    armed_mask = out["armed"].fillna(False).astype(bool)
    out["armed_from_ts"] = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns, UTC]")
    out["valid_until_ts"] = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns, UTC]")
    out.loc[armed_mask, "armed_from_ts"] = ts.loc[armed_mask] + timedelta(minutes=int(timeframe_minutes))

    if order_validity_policy == "session_window_end":
        for idx in out.index[armed_mask]:
            armed_from = out.at[idx, "armed_from_ts"]
            if pd.isna(armed_from):
                continue
            try:
                out.at[idx, "valid_until_ts"] = session_window_end_for_ts(
                    armed_from,
                    session_windows,
                    session_timezone,
                )
            except ValueError:
                out.at[idx, "valid_until_ts"] = pd.NaT
    elif order_validity_policy == "fixed_minutes":
        out.loc[armed_mask, "valid_until_ts"] = (
            out.loc[armed_mask, "armed_from_ts"] + timedelta(minutes=int(order_validity_minutes))
        )
    elif order_validity_policy == "fixed_bars":
        out.loc[armed_mask, "valid_until_ts"] = (
            out.loc[armed_mask, "armed_from_ts"]
            + timedelta(minutes=int(timeframe_minutes) * int(order_validity_bars))
        )
    elif order_validity_policy == "session_end":
        # Backward-compatible alias for existing shared policy naming.
        for idx in out.index[armed_mask]:
            armed_from = out.at[idx, "armed_from_ts"]
            if pd.isna(armed_from):
                continue
            try:
                out.at[idx, "valid_until_ts"] = session_window_end_for_ts(
                    armed_from,
                    session_windows,
                    session_timezone,
                )
            except ValueError:
                out.at[idx, "valid_until_ts"] = pd.NaT
    else:
        raise ValueError(
            f"unsupported order_validity_policy={order_validity_policy!r} "
            "(allowed: session_window_end|session_end|fixed_minutes|fixed_bars)"
        )

    out["valid_window_ok"] = False
    out.loc[armed_mask, "valid_window_ok"] = (
        out.loc[armed_mask, "valid_until_ts"] > out.loc[armed_mask, "armed_from_ts"]
    ).fillna(False)
    return out
