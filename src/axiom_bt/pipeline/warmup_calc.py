"""Warmup calculation helpers for the pipeline.

Warmup is defined in candles. Conversion to days is only for data fetch windows
and uses session-aware bars-per-day (RTH vs RAW).
"""

from __future__ import annotations

import math


class WarmupError(ValueError):
    """Raised when warmup parameters are invalid."""


def bars_per_day(timeframe_minutes: int, session_mode: str) -> int:
    """Compute bars per day based on timeframe and session mode.

    Args:
        timeframe_minutes: Length of one candle in minutes.
        session_mode: "rth" for regular hours (6.5h), "raw" for 24h.

    Returns:
        Integer bars per day (>=1).

    Raises:
        WarmupError: if timeframe_minutes <= 0 or session_mode unknown.
    """
    if timeframe_minutes <= 0:
        raise WarmupError("timeframe_minutes must be > 0")

    mode = (session_mode or "").lower()
    if mode == "rth":
        minutes = 6.5 * 60
    elif mode == "raw":
        minutes = 24 * 60
    else:
        raise WarmupError(f"unsupported session_mode '{session_mode}' (expected rth or raw)")

    return max(1, int(minutes / timeframe_minutes))


def warmup_days_from_bars(required_warmup_bars: int, timeframe_minutes: int, session_mode: str) -> int:
    """Convert warmup bars to days using session-aware bars/day (ceil division).

    Args:
        required_warmup_bars: Indicator warmup requirement in candles (>=0).
        timeframe_minutes: Length of one candle in minutes.
        session_mode: Session mode (rth/raw).

    Returns:
        Warmup days (int >=0).

    Raises:
        WarmupError: for invalid inputs.
    """
    if required_warmup_bars < 0:
        raise WarmupError("required_warmup_bars must be >= 0")

    bpd = bars_per_day(timeframe_minutes, session_mode)
    return int(math.ceil(required_warmup_bars / bpd))
