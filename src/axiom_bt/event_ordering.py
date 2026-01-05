"""
Event Ordering Rules - Compound Sizing Phase 2 (F1-C2)

Implements deterministic, shuffle-invariant event ordering for the event engine.

Key Rule (A1): EXIT events MUST be processed before ENTRY events at the same timestamp.
This ensures equity is updated (from exits) before calculating position size (for entries).

Ordering Rules (Deterministic Tie-Breakers):
1. timestamp (ascending)
2. event_kind priority (EXIT=0, ENTRY=1)
3. symbol (ascending)
4. template_id (ascending)
5. side (BUY before SELL for determinism)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence
import pandas as pd


class EventKind(Enum):
    """Event types for trade execution."""
    EXIT = 0   # Lower priority = processed first
    ENTRY = 1  # Higher priority = processed second


@dataclass(frozen=True)
class TradeEvent:
    """
    Immutable event representing an entry or exit action.
    
    This is a lightweight wrapper for ordering - actual trade logic
    lives in TradeTemplate and will be processed by the event engine.
    """
    timestamp: pd.Timestamp
    kind: EventKind
    symbol: str
    template_id: str
    side: str  # "BUY" or "SELL"
    price: float
    
    def __post_init__(self):
        """Validate event."""
        if self.price <= 0:
            raise ValueError(f"price must be positive, got {self.price}")
    
    def _sort_key(self) -> tuple:
        """
        Generate deterministic sort key following ordering rules.
        
        Returns tuple for stable sorting:
        (timestamp, event_kind_priority, symbol, template_id, side)
        """
        return (
            self.timestamp,              # 1. Time (earliest first)
            self.kind.value,             # 2. EXIT(0) before ENTRY(1)
            self.symbol,                 # 3. Symbol alphabetically
            self.template_id,            # 4. Template ID
            self.side,                   # 5. BUY before SELL
        )


def order_events(events: Sequence[TradeEvent]) -> list[TradeEvent]:
    """
    Order events deterministically following A1 rules.
    
    Ordering guarantee:
    - At same timestamp: EXIT processed before ENTRY
    - Deterministic: same input → same output
    - Shuffle-invariant: input order doesn't matter
    
    Args:
        events: Sequence of TradeEvent objects
        
    Returns:
        Sorted list of events (stable, deterministic)
        
    Example:
        >>> events = [
        ...     TradeEvent(ts1, ENTRY, "AAPL", "id1", "BUY", 150.0),
        ...     TradeEvent(ts1, EXIT, "AAPL", "id0", "SELL", 155.0),
        ... ]
        >>> ordered = order_events(events)
        >>> ordered[0].kind == EventKind.EXIT  # EXIT first
        True
    """
    if not events:
        return []
    
    # Sort using stable sort key
    # Python's sort is stable, so equal keys preserve original relative order
    # But we don't rely on that - our key is fully specified (no ties)
    return sorted(events, key=lambda e: e._sort_key())


def validate_event_ordering(events: Sequence[TradeEvent]) -> bool:
    """
    Validate that events follow A1 ordering rules.
    
    Checks:
    - At each timestamp, all EXITs come before all ENTRYs
    - Events are in ascending timestamp order
    
    Args:
        events: Sequence of events (assumed pre-sorted)
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If ordering violation found (with details)
    """
    if not events:
        return True
    
    # Check ascending timestamps (monotonic)
    for i in range(1, len(events)):
        if events[i].timestamp < events[i-1].timestamp:
            raise ValueError(
                f"Timestamps not monotonic: {events[i-1].timestamp} → {events[i].timestamp}"
            )
    
    # Check A1 rule: within same timestamp, EXIT before ENTRY
    current_ts = None
    seen_entry_at_current_ts = False
    
    for event in events:
        if event.timestamp != current_ts:
            # New timestamp - reset
            current_ts = event.timestamp
            seen_entry_at_current_ts = False
        
        if event.kind == EventKind.EXIT:
            if seen_entry_at_current_ts:
                raise ValueError(
                    f"A1 VIOLATION: EXIT after ENTRY at {current_ts} "
                    f"(event: {event.template_id})"
                )
        elif event.kind == EventKind.ENTRY:
            seen_entry_at_current_ts = True
    
    return True
