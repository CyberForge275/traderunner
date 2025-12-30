"""
Order validity window calculation for replay fills.

CRITICAL: This module ensures orders have non-zero validity windows
to enable fills in bar-based replay engines.

The November 2024 successful run had ~35 minute validity windows
extending to session end, achieving 94% fill rate. This module
implements that proven behavior.
"""
from datetime import timedelta
from typing import Tuple
import pandas as pd

from strategies.inside_bar.config import SessionFilter


def calculate_validity_window(
    signal_ts: pd.Timestamp,
    timeframe_minutes: int,
    session_filter: SessionFilter,
    session_timezone: str,
    validity_policy: str,
    validity_minutes: int = 60,
    valid_from_policy: str = "signal_ts",
) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    Calculate order validity window.

    CRITICAL: session_end is calculated from valid_from, NOT signal_ts,
    to prevent zero-duration windows at session boundaries.

    Example Problem (without this fix):
        - Signal at 15:55 Berlin
        - valid_from_policy = "next_bar" → valid_from = 16:00
        - Session 1 ends at 16:00
        - If we calculate session_end from signal_ts → valid_to = 16:00
        - Result: valid_to == valid_from → ZERO DURATION → No fills!

    Solution:
        - Calculate session_end from valid_from
        - If valid_from is outside session, reject order entirely

    Args:
        signal_ts: Signal timestamp (MUST be timezone-aware)
        timeframe_minutes: Bar duration (e.g., 5 for M5)
        session_filter: SessionFilter instance
        session_timezone: Timezone for session checks (e.g., "Europe/Berlin")
        validity_policy: "session_end" | "fixed_minutes" | "one_bar"
        validity_minutes: Minutes for fixed_minutes policy
        valid_from_policy: "signal_ts" | "next_bar"

    Returns:
        (valid_from, valid_to) tuple where valid_to > valid_from

    Raises:
        ValueError: If signal not in session, window invalid, or valid_from crosses session boundary

    Examples:
        >>> # Signal at 15:30, session_end policy
        >>> signal_ts = pd.Timestamp("2025-11-28 15:30:00", tz="Europe/Berlin")
        >>> valid_from, valid_to = calculate_validity_window(
        ...     signal_ts=signal_ts,
        ...     timeframe_minutes=5,
        ...     session_filter=SessionFilter.from_strings(["15:00-16:00"]),
        ...     session_timezone="Europe/Berlin",
        ...     validity_policy="session_end",
        ...     valid_from_policy="signal_ts"
        ... )
        >>> assert valid_from == signal_ts
        >>> assert valid_to == pd.Timestamp("2025-11-28 16:00:00", tz="Europe/Berlin")
        >>> assert (valid_to - valid_from).total_seconds() == 1800  # 30 minutes
    """
    # Validate timezone-aware timestamp
    if signal_ts.tz is None:
        raise ValueError(
            f"signal_ts must be timezone-aware: {signal_ts}. "
            "All timestamps must have timezone info for validity calculation."
        )

    # Calculate valid_from based on policy
    if valid_from_policy == "next_bar":
        valid_from = signal_ts + timedelta(minutes=timeframe_minutes)
    elif valid_from_policy == "signal_ts":
        valid_from = signal_ts
    else:
        raise ValueError(
            f"Unknown valid_from_policy: {valid_from_policy}. "
            "Must be 'signal_ts' or 'next_bar'."
        )

    # Calculate valid_to based on validity_policy
    if validity_policy == "one_bar":
        # Order valid for one bar duration
        valid_to = valid_from + timedelta(minutes=timeframe_minutes)

    elif validity_policy == "session_end":
        # CRITICAL FIX: Use valid_from, not signal_ts
        # This prevents zero-duration windows when valid_from crosses session boundary
        try:
            session_end = session_filter.get_session_end(valid_from, session_timezone)
        except ValueError as e:
            # SessionFilter raises ValueError for naive timestamps
            raise ValueError(
                f"Session filter error for valid_from ({valid_from}): {e}"
            )

        if session_end is None:
            # valid_from is outside session - this can happen with next_bar policy
            # when signal occurs near session end
            raise ValueError(
                f"valid_from ({valid_from}) not in any session window. "
                f"Signal was at {signal_ts}, but valid_from_policy='{valid_from_policy}' "
                f"moved it outside the session. Cannot use 'session_end' policy. "
                "Order rejected."
            )

        valid_to = session_end

        # Additional safety check
        if valid_to <= valid_from:
            raise ValueError(
                f"valid_from ({valid_from}) is at or after session_end ({session_end}). "
                f"Signal at {signal_ts} is too close to session boundary. "
                "Order rejected to prevent zero-duration window."
            )

    elif validity_policy == "fixed_minutes":
        # Order valid for fixed number of minutes
        valid_to = valid_from + timedelta(minutes=validity_minutes)

        # Optional: Clamp to session end if valid_from is in session
        try:
            session_end = session_filter.get_session_end(valid_from, session_timezone)
            if session_end and valid_to > session_end:
                # Clamp to session boundary
                valid_to = session_end
        except ValueError:
            # valid_from not in session or naive timestamp - ignore clamping
            pass

    else:
        raise ValueError(
            f"Unknown validity_policy: {validity_policy}. "
            "Must be 'session_end', 'fixed_minutes', or 'one_bar'."
        )

    # Final validation: ensure non-zero duration
    if valid_to <= valid_from:
        raise ValueError(
            f"Invalid validity window: valid_to ({valid_to}) <= valid_from ({valid_from}). "
            f"Cannot create order with zero or negative duration. "
            f"This should never happen if logic is correct. "
            f"signal_ts={signal_ts}, policy={validity_policy}, valid_from_policy={valid_from_policy}"
        )

    return (valid_from, valid_to)
