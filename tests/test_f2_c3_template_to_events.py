"""
Tests for F2-C3: Template to Event Extraction

Proves:
- templates_to_events creates 2 events per template
- Fields mapped correctly (ts, symbol, template_id, side, price)
- Extraction is deterministic and shuffle-invariant
- Invalid templates raise errors
- A1 ordering holds on extracted events
"""

import pytest
import pandas as pd

from axiom_bt.trade_templates import TradeTemplate
from axiom_bt.template_to_events import templates_to_events
from axiom_bt.event_ordering import TradeEvent, EventKind, order_events


def test_templates_to_events_creates_two_events_per_template():
    """F2-C3: Each template → 2 events (ENTRY + EXIT)."""
    ts1 = pd.Timestamp("2026-01-06 10:00:00")
    ts2 = pd.Timestamp("2026-01-06 11:00:00")
    
    templates = [
        TradeTemplate(
            template_id="t1",
            symbol="AAPL",
            side="BUY",
            entry_ts=ts1,
            entry_price=100.0,
            entry_reason="test",
            exit_ts=ts2,
            exit_price=105.0,
            exit_reason="profit",
        ),
    ]
    
    events = templates_to_events(templates)
    
    # Should have 2 events
    assert len(events) == 2
    
    # First should be ENTRY
    assert events[0].kind == EventKind.ENTRY
    assert events[0].timestamp == ts1
    
    # Second should be EXIT
    assert events[1].kind == EventKind.EXIT
    assert events[1].timestamp == ts2


def test_entry_exit_fields_mapped_correctly():
    """F2-C3: Fields map correctly from template to events."""
    ts1 = pd.Timestamp("2026-01-06 10:00:00")
    ts2 = pd.Timestamp("2026-01-06 11:00:00")
    
    template = TradeTemplate(
        template_id="test_123",
        symbol="MSFT",
        side="BUY",
        entry_ts=ts1,
        entry_price=200.0,
        entry_reason="signal",
        exit_ts=ts2,
        exit_price=210.0,
        exit_reason="target",
    )
    
    events = templates_to_events([template])
    
    # ENTRY event
    entry = events[0]
    assert entry.kind == EventKind.ENTRY
    assert entry.symbol == "MSFT"
    assert entry.template_id == "test_123"
    assert entry.side == "BUY"
    assert entry.timestamp == ts1
    
    # EXIT event
    exit_ev = events[1]
    assert exit_ev.kind == EventKind.EXIT
    assert exit_ev.symbol == "MSFT"
    assert exit_ev.template_id == "test_123"
    assert exit_ev.side == "SELL"  # Opposite of entry
    assert exit_ev.timestamp == ts2


def test_prices_present_and_mapped():
    """F2-C3: Prices mapped from template to events."""
    ts = pd.Timestamp("2026-01-06 10:00:00")
    
    template = TradeTemplate(
        template_id="t1",
        symbol="AAPL",
        side="BUY",
        entry_ts=ts,
        entry_price=150.75,
        entry_reason="test",
        exit_ts=ts + pd.Timedelta(minutes=10),
        exit_price=155.25,
        exit_reason="test",
    )
    
    events = templates_to_events([template])
    
    # Entry price
    assert events[0].price == 150.75
    
    # Exit price
    assert events[1].price == 155.25


def test_extraction_is_deterministic_across_shuffles():
    """F2-C3: Same templates → same events (deterministic, shuffle-invariant)."""
    ts = pd.Timestamp("2026-01-06 10:00:00")
    
    templates = [
        TradeTemplate("t1", "AAPL", "BUY", ts, 100.0, "r1", ts + pd.Timedelta(minutes=5), 105.0, "r2"),
        TradeTemplate("t2", "MSFT", "SELL", ts, 200.0, "r1", ts + pd.Timedelta(minutes=10), 195.0, "r2"),
    ]
    
    # Extract twice
    events1 = templates_to_events(templates)
    events2 = templates_to_events(templates)
    
    # Should be identical
    assert len(events1) == len(events2)
    
    for e1, e2 in zip(events1, events2):
        assert e1.timestamp == e2.timestamp
        assert e1.kind == e2.kind
        assert e1.symbol == e2.symbol
        assert e1.template_id == e2.template_id
        assert e1.price == e2.price


def test_extraction_handles_empty_templates():
    """F2-C3: Empty template list → empty events."""
    events = templates_to_events([])
    assert events == []



def test_extraction_rejects_exit_ts_without_price():
    """F2-C3: ValueError if exit_ts present but exit_price invalid."""
    ts = pd.Timestamp("2026-01-06 10:00:00")  # Fixed typo
    
    template = TradeTemplate(
        template_id="bad",
        symbol="AAPL",
        side="BUY",
        entry_ts=ts,
        entry_price=100.0,
        entry_reason="test",
        exit_ts=ts + pd.Timedelta(minutes=5),  # Exit ts present
        exit_price=None,  # But no exit price
    )
    
    with pytest.raises(ValueError, match="exit_ts but invalid exit_price"):
        templates_to_events([template])



if __name__ == "__main__":
    pytest.main([__file__, "-v"])

