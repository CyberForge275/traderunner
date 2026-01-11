"""Helpers for day-wise partitioning and execution of trade events.

Used by the compound path to process events session-by-session in market_tz
with deterministic ordering and cash carry-forward.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple
from datetime import date

import pandas as pd

from axiom_bt.event_ordering import TradeEvent, order_events


def _to_market_date(ts: pd.Timestamp, market_tz: str) -> date:
    """Convert timestamp to market-local date.

    - If ts is naive, treat as UTC for determinism (no hidden local TZ).
    - Then convert to market_tz and take date().
    """

    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert(market_tz).date()


def partition_events_by_market_day(
    events: Sequence[TradeEvent], market_tz: str
) -> List[Tuple[date, List[TradeEvent]]]:
    """Partition events by market-local day with deterministic ordering.

    Steps:
    1) Globally order events using order_events (timestamp, kind, symbol,...).
    2) Compute partition key = local date in market_tz.
    3) Return list of (date, events_sorted) in ascending date order.
       Each partition is already ordered by order_events.
    """

    if not events:
        return []

    ordered = order_events(events)

    parts: List[Tuple[date, List[TradeEvent]]] = []
    current_day = None
    bucket: List[TradeEvent] = []

    for ev in ordered:
        day = _to_market_date(ev.timestamp, market_tz)
        if current_day is None:
            current_day = day
        if day != current_day:
            parts.append((current_day, bucket))
            bucket = []
            current_day = day
        bucket.append(ev)

    if bucket:
        parts.append((current_day, bucket))

    return parts


def process_daywise(
    engine,
    events: Sequence[TradeEvent],
    market_tz: str,
    initial_cash: float,
    *,
    slippage_bps: float = 0.0,
    commission_bps: float = 0.0,
):
    """Process events day-by-day carrying cash forward.

    Returns tuple (processed_events, ledger_rows, final_cash, num_partitions).

    ledger_rows: list of dicts {seq, timestamp, cash}, includes START row (seq=0).
    processed_events: list of ProcessedEvent objects in the order processed.
    """

    parts = partition_events_by_market_day(events, market_tz)

    cash = float(initial_cash)
    processed_all = []
    ledger_rows = []

    # START row
    start_ts = parts[0][1][0].timestamp if parts else None
    ledger_rows.append({"seq": 0, "timestamp": start_ts, "cash": cash})
    seq = 0

    for day, day_events in parts:
        result = engine.process(day_events, initial_cash=cash)
        processed_all.extend(result.processed)
        cash = result.stats.get("final_cash", cash)

        # End-of-day ledger entry using last event ts of the day
        end_ts = day_events[-1].timestamp if day_events else None
        seq += 1
        ledger_rows.append({"seq": seq, "timestamp": end_ts, "cash": cash})

    return processed_all, ledger_rows, cash, len(parts)
