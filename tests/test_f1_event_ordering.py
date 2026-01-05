"""
Tests for F1-C2: Event Ordering Rules (A1)

Proves:
- A1 rule: EXIT before ENTRY at same timestamp
- Determinism: same input → same output
- Shuffle-invariance: input order doesn't matter
- Stable tie-breakers
"""

import pytest
import pandas as pd

from axiom_bt.event_ordering import (
    TradeEvent,
    EventKind,
    order_events,
    validate_event_ordering,
)


def test_ordering_exit_before_entry_same_timestamp():
    """F1-C2: A1 rule - EXIT must be processed before ENTRY at same timestamp."""
    ts = pd.Timestamp("2026-01-05 10:00:00")
    
    # Create events in "wrong" order (ENTRY first, EXIT second)
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 150.0),
        TradeEvent(ts, EventKind.EXIT, "AAPL", "id0", "SELL", 155.0),
    ]
    
    # Order them
    ordered = order_events(events)
    
    # EXIT must come first
    assert len(ordered) == 2
    assert ordered[0].kind == EventKind.EXIT
    assert ordered[1].kind == EventKind.ENTRY


def test_ordering_is_deterministic_across_shuffles():
    """F1-C2: Same events in different order produce identical sorted result."""
    ts1 = pd.Timestamp("2026-01-05 10:00:00")
    ts2 = pd.Timestamp("2026-01-05 11:00:00")
    
    # Original order
    events_v1 = [
        TradeEvent(ts2, EventKind.ENTRY, "AAPL", "id3", "BUY", 160.0),
        TradeEvent(ts1, EventKind.EXIT, "AAPL", "id1", "SELL", 155.0),
        TradeEvent(ts1, EventKind.ENTRY, "AAPL", "id2", "BUY", 150.0),
        TradeEvent(ts2, EventKind.EXIT, "AAPL", "id4", "SELL", 165.0),
    ]
    
    # Shuffled order (completely reversed)
    events_v2 = list(reversed(events_v1))
    
    # Order both
    ordered_v1 = order_events(events_v1)
    ordered_v2 = order_events(events_v2)
    
    # Results must be IDENTICAL
    assert len(ordered_v1) == len(ordered_v2)
    
    for i, (e1, e2) in enumerate(zip(ordered_v1, ordered_v2)):
        assert e1.timestamp == e2.timestamp, f"Mismatch at index {i}"
        assert e1.kind == e2.kind, f"Mismatch at index {i}"
        assert e1.template_id == e2.template_id, f"Mismatch at index {i}"
    
    # Verify expected order:
    # ts1: EXIT(id1), ENTRY(id2)
    # ts2: EXIT(id4), ENTRY(id3)
    assert ordered_v1[0].timestamp == ts1 and ordered_v1[0].kind == EventKind.EXIT
    assert ordered_v1[1].timestamp == ts1 and ordered_v1[1].kind == EventKind.ENTRY
    assert ordered_v1[2].timestamp == ts2 and ordered_v1[2].kind == EventKind.EXIT
    assert ordered_v1[3].timestamp == ts2 and ordered_v1[3].kind == EventKind.ENTRY


def test_ordering_stable_tiebreakers():
    """F1-C2: Within same timestamp+kind, use stable tie-breakers (symbol, id)."""
    ts = pd.Timestamp("2026-01-05 10:00:00")
    
    # Multiple ENTRYs at same timestamp
    events = [
        TradeEvent(ts, EventKind.ENTRY, "MSFT", "id2", "BUY", 300.0),
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 150.0),
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id3", "BUY", 151.0),
    ]
    
    ordered = order_events(events)
    
    # Should be ordered by: timestamp, kind, symbol, template_id
    assert ordered[0].symbol == "AAPL" and ordered[0].template_id == "id1"
    assert ordered[1].symbol == "AAPL" and ordered[1].template_id == "id3"
    assert ordered[2].symbol == "MSFT" and ordered[2].template_id == "id2"


def test_ordering_validates_correctly():
    """F1-C2: validate_event_ordering accepts correct ordering."""
    ts1 = pd.Timestamp("2026-01-05 10:00:00")
    ts2 = pd.Timestamp("2026-01-05 11:00:00")
    
    # Correctly ordered events
    events = [
        TradeEvent(ts1, EventKind.EXIT, "AAPL", "id1", "SELL", 155.0),
        TradeEvent(ts1, EventKind.ENTRY, "AAPL", "id2", "BUY", 150.0),
        TradeEvent(ts2, EventKind.EXIT, "AAPL", "id3", "SELL", 165.0),
        TradeEvent(ts2, EventKind.ENTRY, "AAPL", "id4", "BUY", 160.0),
    ]
    
    # Should not raise
    assert validate_event_ordering(events) == True


def test_ordering_validation_rejects_a1_violation():
    """F1-C2: validate_event_ordering rejects ENTRY before EXIT at same timestamp."""
    ts = pd.Timestamp("2026-01-05 10:00:00")
    
    # WRONG order: ENTRY before EXIT
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 150.0),
        TradeEvent(ts, EventKind.EXIT, "AAPL", "id2", "SELL", 155.0),  # Should be first!
    ]
    
    # Should raise ValueError with A1 violation message
    with pytest.raises(ValueError, match="A1 VIOLATION"):
        validate_event_ordering(events)


def test_ordering_validation_rejects_non_monotonic():
    """F1-C2: validate_event_ordering rejects out-of-order timestamps."""
    ts1 = pd.Timestamp("2026-01-05 10:00:00")
    ts2 = pd.Timestamp("2026-01-05 09:00:00")  # Earlier!
    
    # Timestamps not monotonic
    events = [
        TradeEvent(ts1, EventKind.ENTRY, "AAPL", "id1", "BUY", 150.0),
        TradeEvent(ts2, EventKind.ENTRY, "AAPL", "id2", "BUY", 145.0),  # Goes backward
    ]
    
    # Should raise ValueError
    with pytest.raises(ValueError, match="Timestamps not monotonic"):
        validate_event_ordering(events)


def test_event_immutability():
    """F1-C2: TradeEvent is frozen (immutable)."""
    event = TradeEvent(
        timestamp=pd.Timestamp("2026-01-05 10:00:00"),
        kind=EventKind.ENTRY,
        symbol="AAPL",
        template_id="id1",
        side="BUY",
        price=150.0,
    )
    
    # Should raise because frozen
    with pytest.raises(Exception):  # FrozenInstanceError
        event.price = 200.0


def test_order_events_empty_input():
    """F1-C2: order_events handles empty input gracefully."""
    result = order_events([])
    assert result == []


def test_order_events_single_event():
    """F1-C2: order_events handles single event."""
    event = TradeEvent(
        timestamp=pd.Timestamp("2026-01-05 10:00:00"),
        kind=EventKind.ENTRY,
        symbol="AAPL",
        template_id="id1",
        side="BUY",
        price=150.0,
    )
    
    result = order_events([event])
    assert len(result) == 1
    assert result[0] == event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
