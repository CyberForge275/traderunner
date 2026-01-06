"""
Tests for F2-C1: Cash-only Equity Tracker and Qty-at-Entry

Proves:
- CashEquityTracker equity() is cash-only (no MTM)
- Qty calculation policies (fixed_qty, floor-based)
- Entry/exit fill processing updates cash
- Rejections when qty=0 or no position
- Round-trip buy/sell maintains determinism
"""

import pytest
import pandas as pd

from axiom_bt.event_engine import (
    EventEngine,
    CashEquityTracker,
    Position,
    ProcessedEvent,
    EngineResult,
)
from axiom_bt.event_ordering import TradeEvent, EventKind


def test_cash_equity_tracker_equity_is_cash_only():
    """F2-C1: Equity is cash_only (ignores unrealized MTM of open positions)."""
    tracker = CashEquityTracker(cash=1000.0)
    
    # Open a position
    tracker.apply_fill("BUY", "AAPL", qty=5.0, price=100.0)
    
    # Cash decreased by cost
    assert tracker.cash == 500.0  # 1000 - (5 * 100)
    
    # Equity is cash-only (ignores position value)
    equity = tracker.equity()
    assert equity == 500.0, "Equity should be cash-only, not MTM"
    
    # Even if price moved to 200, equity stays cash-only
    # (no price update in tracker, it's cash-only)
    assert tracker.equity() == 500.0


def test_qty_policy_fixed_qty_used():
    """F2-C1: When fixed_qty set, use it for all entries."""
    engine = EventEngine(fixed_qty=10.0)
    
    ts = pd.Timestamp("2026-01-06 10:00:00")
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 150.0),
    ]
    
    result = engine.process(events, initial_cash=10000.0)
    
    # Qty should be fixed_qty=10.0
    assert len(result.processed) == 1
    proc = result.processed[0]
    assert proc.qty == 10.0
    assert proc.status == "filled"
    
    # Cash should decrease by qty * price
    assert proc.cash_after == 10000.0 - (10.0 * 150.0)
    assert proc.cash_after == 8500.0


def test_qty_policy_floor_cash_div_price():
    """F2-C1: Default policy uses floor(cash / price)."""
    engine = EventEngine()  # No fixed_qty
    
    ts = pd.Timestamp("2026-01-06 10:00:00")
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 123.0),
    ]
    
    result = engine.process(events, initial_cash=1000.0)
    
    # Qty = floor(1000 / 123) = floor(8.130) = 8
    assert len(result.processed) == 1
    proc = result.processed[0]
    assert proc.qty == 8.0
    assert proc.status == "filled"
    
    # Cash = 1000 - (8 * 123) = 1000 - 984 = 16
    assert proc.cash_after == 16.0


def test_entry_rejected_when_qty_zero():
    """F2-C1: Entry rejected when cash < price (qty=0)."""
    engine = EventEngine()
    
    ts = pd.Timestamp("2026-01-06 10:00:00")
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 1500.0),  # Price > cash
    ]
    
    result = engine.process(events, initial_cash=1000.0)
    
    # Qty = floor(1000 / 1500) = 0 → rejected
    assert len(result.processed) == 1
    proc = result.processed[0]
    assert proc.status == "rejected"
    assert proc.reason == "insufficient_cash_for_min_qty"
    assert proc.qty == 0.0
    
    # Cash unchanged
    assert proc.cash_after == 1000.0


def test_engine_updates_cash_on_buy_and_sell_roundtrip():
    """
    F2-C1: Full round-trip (BUY then SELL) updates cash correctly.
    
    Start: cash=1000
    BUY 5 @ 100 → cash=500
    SELL 5 @ 110 → cash=1050
    """
    engine = EventEngine(fixed_qty=5.0)
    
    ts1 = pd.Timestamp("2026-01-06 10:00:00")
    ts2 = pd.Timestamp("2026-01-06 11:00:00")
    
    events = [
        TradeEvent(ts1, EventKind.ENTRY, "AAPL", "id1", "BUY", 100.0),
        TradeEvent(ts2, EventKind.EXIT, "AAPL", "id2", "SELL", 110.0),
    ]
    
    result = engine.process(events, initial_cash=1000.0)
    
    # Two events processed
    assert len(result.processed) == 2
    
    # Event 1: BUY
    buy_proc = result.processed[0]
    assert buy_proc.kind == EventKind.ENTRY
    assert buy_proc.status == "filled"
    assert buy_proc.qty == 5.0
    assert buy_proc.price == 100.0
    assert buy_proc.cash_after == 500.0  # 1000 - (5*100)
    
    # Event 2: SELL
    sell_proc = result.processed[1]
    assert sell_proc.kind == EventKind.EXIT
    assert sell_proc.status == "filled"
    assert sell_proc.qty == 5.0  # Uses position qty
    assert sell_proc.price == 110.0
    assert sell_proc.cash_after == 1050.0  # 500 + (5*110)
    
    # Final stats
    assert result.stats["final_cash"] == 1050.0
    assert result.stats["final_equity"] == 1050.0  # Cash-only


def test_exit_rejected_if_no_position():
    """F2-C1: EXIT rejected if no open position for symbol."""
    engine = EventEngine()
    
    ts = pd.Timestamp("2026-01-06 10:00:00")
    events = [
        TradeEvent(ts, EventKind.EXIT, "AAPL", "id1", "SELL", 150.0),  # No entry first
    ]
    
    result = engine.process(events, initial_cash=1000.0)
    
    # Rejected: no position
    assert len(result.processed) == 1
    proc = result.processed[0]
    assert proc.status == "rejected"
    assert proc.reason == "no_position_to_exit"
    assert proc.qty == 0.0
    
    # Cash unchanged
    assert proc.cash_after == 1000.0


def test_cash_equity_tracker_accumulates_positions():
    """F2-C1: Multiple entries accumulate qty."""
    tracker = CashEquityTracker(cash=10000.0)
    
    # First entry
    tracker.apply_fill("BUY", "AAPL", 5.0, 100.0)
    assert tracker.get_position_qty("AAPL") == 5.0
    assert tracker.cash == 9500.0
    
    # Second entry (accumulate)
    tracker.apply_fill("BUY", "AAPL", 3.0, 110.0)
    assert tracker.get_position_qty("AAPL") == 8.0  # 5 + 3
    assert tracker.cash == 9500.0 - 330.0  # 9500 - (3*110)
    assert tracker.cash == 9170.0


def test_engine_deterministic_results():
    """F2-C1: Same events → same result (determinism)."""
    engine = EventEngine(fixed_qty=5.0)
    
    ts = pd.Timestamp("2026-01-06 10:00:00")
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 100.0),
    ]
    
    # Run twice
    result1 = engine.process(events, initial_cash=1000.0)
    result2 = engine.process(events, initial_cash=1000.0)
    
    # Results identical
    assert len(result1.processed) == len(result2.processed)
    assert result1.processed[0].qty == result2.processed[0].qty
    assert result1.processed[0].cash_after == result2.processed[0].cash_after
    assert result1.stats["final_cash"] == result2.stats["final_cash"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
