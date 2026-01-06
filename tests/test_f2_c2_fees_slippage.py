"""
Tests for F2-C2: Fees & Slippage

Proves:
- slippage_bps=0, commission_bps=0 matches F2-C1 (backward compat)
- BUY slippage increases effective price
- SELL slippage decreases effective price
- Commission calculated correctly on notional
- Cash updates include both slippage and fees
"""

import pytest
import pandas as pd

from axiom_bt.event_engine import EventEngine
from axiom_bt.event_ordering import TradeEvent, EventKind


def test_no_fees_no_slippage_matches_f2_c1_cash_math():
    """F2-C2: Defaults (0,0) produce same cash as F2-C1 (backward compat)."""
    engine_no_fees = EventEngine(slippage_bps=0.0, commission_bps=0.0, fixed_qty=10.0)
    
    ts = pd.Timestamp("2026-01-06 10:00:00")
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 100.0),
    ]
    
    result = engine_no_fees.process(events, initial_cash=2000.0)
    
    # qty=10, price=100, no slip/fee → cost = 1000
    proc = result.processed[0]
    assert proc.status == "filled"
    assert proc.qty == 10.0
    assert proc.price == 100.0
    assert proc.effective_price == 100.0  # No slippage
    assert proc.fee == 0.0
    assert proc.cash_after == 1000.0  # 2000 - 1000


def test_buy_slippage_increases_effective_price():
    """F2-C2: BUY with slippage: effective_price = price * (1 + slippage_bps/10000)."""
    # slippage_bps=10 → 0.001 = 0.1%
    engine = EventEngine(slippage_bps=10.0, commission_bps=0.0, fixed_qty=10.0)
    
    ts = pd.Timestamp("2026-01-06 10:00:00")
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 100.0),
    ]
    
    result = engine.process(events, initial_cash=2000.0)
    
    proc = result.processed[0]
    assert proc.status == "filled"
    assert proc.price == 100.0
    
    # F2-C2: effective = 100 * (1 + 10/10000) = 100 * 1.001 = 100.1
    assert proc.effective_price == pytest.approx(100.1)
    
    # Cost = qty * effective_price = 10 * 100.1 = 1001
    assert proc.cash_after == pytest.approx(999.0)  # 2000 - 1001


def test_sell_slippage_decreases_effective_price():
    """F2-C2: SELL with slippage: effective_price = price * (1 - slippage_bps/10000)."""
    # slippage_bps=10 → 0.001 = 0.1%
    engine = EventEngine(slippage_bps=10.0, commission_bps=0.0, fixed_qty=10.0)
    
    ts1 = pd.Timestamp("2026-01-06 10:00:00")
    ts2 = pd.Timestamp("2026-01-06 11:00:00")
    
    # BUY first (no slippage for setup simplicity - set slippage after)
    engine_setup = EventEngine(slippage_bps=0.0, commission_bps=0.0, fixed_qty=10.0)
    events_buy = [TradeEvent(ts1, EventKind.ENTRY, "AAPL", "id1", "BUY", 100.0)]
    result_buy = engine_setup.process(events_buy, initial_cash=2000.0)
    cash_after_buy = result_buy.processed[0].cash_after  # 1000
    
    # Now SELL with slippage
    events_sell = [
        TradeEvent(ts1, EventKind.ENTRY, "AAPL", "id1", "BUY", 100.0),  # Setup position
        TradeEvent(ts2, EventKind.EXIT, "AAPL", "id2", "SELL", 100.0),   # SELL with slippage
    ]
    
    engine_with_slip = EventEngine(slippage_bps=10.0, commission_bps=0.0, fixed_qty=10.0)
    result = engine_with_slip.process(events_sell, initial_cash=2000.0)
    
    # Second event is SELL
    sell_proc = result.processed[1]
    assert sell_proc.kind == EventKind.EXIT
    assert sell_proc.price == 100.0
    
    # F2-C2: effective = 100 * (1 - 10/10000) = 100 * 0.999 = 99.9
    assert sell_proc.effective_price == pytest.approx(99.9)


def test_commission_bps_applied_to_notional():
    """F2-C2: Commission = notional * commission_bps/10000."""
    # commission_bps=5 → 0.0005 = 0.05%
    engine = EventEngine(slippage_bps=0.0, commission_bps=5.0, fixed_qty=10.0)
    
    ts = pd.Timestamp("2026-01-06 10:00:00")
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 100.0),
    ]
    
    result = engine.process(events, initial_cash=2000.0)
    
    proc = result.processed[0]
    assert proc.status == "filled"
    
    # notional = qty * effective_price = 10 * 100 = 1000
    # fee = 1000 * 5/10000 = 1000 * 0.0005 = 0.5
    assert proc.fee == pytest.approx(0.5)
    
    # cash = init - (qty * price + fee) = 2000 - (1000 + 0.5) = 999.5
    assert proc.cash_after == pytest.approx(999.5)


def test_cash_update_buy_includes_fee_and_slippage():
    """F2-C2: BUY cash update = cash - (qty * effective_price + fee)."""
    # slippage_bps=10, commission_bps=5
    engine = EventEngine(slippage_bps=10.0, commission_bps=5.0, fixed_qty=10.0)
    
    ts = pd.Timestamp("2026-01-06 10:00:00")
    events = [
        TradeEvent(ts, EventKind.ENTRY, "AAPL", "id1", "BUY", 100.0),
    ]
    
    result = engine.process(events, initial_cash=2000.0)
    
    proc = result.processed[0]
    
    # Effective price = 100 * (1 + 10/10000) = 100.1
    assert proc.effective_price == pytest.approx(100.1)
    
    # Notional = qty * effective_price = 10 * 100.1 = 1001
    notional = 10 * 100.1
    
    # Fee = 1001 * 5/10000 = 0.5005
    expected_fee = notional * 5 / 10000
    assert proc.fee == pytest.approx(expected_fee)
    
    # Cash = 2000 - (1001 + 0.5005) = 2000 - 1001.5005 = 998.4995
    expected_cash = 2000.0 - (notional + expected_fee)
    assert proc.cash_after == pytest.approx(expected_cash)


def test_cash_update_sell_includes_fee_and_slippage():
    """F2-C2: SELL cash update = cash + (qty * effective_price - fee)."""
    # slippage_bps=10, commission_bps=5
    engine = EventEngine(slippage_bps=10.0, commission_bps=5.0, fixed_qty=10.0)
    
    ts1 = pd.Timestamp("2026-01-06 10:00:00")
    ts2 = pd.Timestamp("2026-01-06 11:00:00")
    
    events = [
        TradeEvent(ts1, EventKind.ENTRY, "AAPL", "id1", "BUY", 100.0),   # Setup
        TradeEvent(ts2, EventKind.EXIT, "AAPL", "id2", "SELL", 110.0),  # SELL
    ]
    
    result = engine.process(events, initial_cash=2000.0)
    
    # BUY first
    buy_proc = result.processed[0]
    cash_after_buy = buy_proc.cash_after
    
    # SELL second
    sell_proc = result.processed[1]
    assert sell_proc.kind == EventKind.EXIT
    
    # Effective price = 110 * (1 - 10/10000) = 110 * 0.999 = 109.89
    assert sell_proc.effective_price == pytest.approx(109.89)
    
    # Notional = qty * effective_price = 10 * 109.89 = 1098.9
    notional = 10 * 109.89
    
    # Fee = 1098.9 * 5/10000 = 0.54945
    expected_fee = notional * 5 / 10000
    assert sell_proc.fee == pytest.approx(expected_fee)
    
    # Cash = cash_after_buy + (1098.9 - 0.54945)
    expected_cash = cash_after_buy + (notional - expected_fee)
    assert sell_proc.cash_after == pytest.approx(expected_cash)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
