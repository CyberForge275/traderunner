"""Date range resolver for backtest UI callbacks."""

from __future__ import annotations

from datetime import datetime, timedelta


def resolve_ui_backtest_range(
    date_mode,
    anchor_date,
    days_back,
    explicit_start,
    explicit_end,
):
    """Resolve UI date inputs to start/end dates (parity with callback semantics)."""
    if date_mode == "days_back":
        if isinstance(anchor_date, str):
            end_date = datetime.fromisoformat(anchor_date).date()
        else:
            end_date = anchor_date
        start_date = end_date - timedelta(days=int(days_back or 30))
    else:
        if isinstance(explicit_start, str):
            start_date = datetime.fromisoformat(explicit_start).date()
        else:
            start_date = explicit_start

        if isinstance(explicit_end, str):
            end_date = datetime.fromisoformat(explicit_end).date()
        else:
            end_date = explicit_end

    return start_date, end_date

