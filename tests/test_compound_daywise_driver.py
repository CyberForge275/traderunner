"""Day-wise compounding driver tests (offline, hermetic)."""

import pandas as pd

from axiom_bt.day_partition import partition_events_by_market_day, process_daywise
from axiom_bt.event_ordering import TradeEvent, EventKind
from axiom_bt.event_engine import EventEngine


def _ev(ts: str, kind: EventKind, template: str, side: str, price: float) -> TradeEvent:
    return TradeEvent(timestamp=pd.Timestamp(ts), kind=kind, symbol="PLTR", template_id=template, side=side, price=price)


def test_partition_uses_market_day_ny():
    # ts1 -> 2025-01-10 09:30 NY, ts2 -> 2025-01-11 09:30 NY
    ts1 = "2025-01-10 14:30:00Z"
    ts2 = "2025-01-11 14:30:00Z"
    events = [
        _ev(ts2, EventKind.ENTRY, "t2", "BUY", 100.0),
        _ev(ts1, EventKind.ENTRY, "t1", "BUY", 100.0),
    ]

    parts = partition_events_by_market_day(events, "America/New_York")

    assert len(parts) == 2
    dates = [d for d, _ in parts]
    assert str(dates[0]) == "2025-01-10"
    assert str(dates[1]) == "2025-01-11"
    # Order inside partition is deterministic (order_events)
    assert parts[0][1][0].template_id == "t1"
    assert parts[1][1][0].template_id == "t2"


def test_cash_carry_across_days():
    # Two days; profit on day1 should increase cash for day2
    day1_entry = _ev("2025-01-10 14:30:00Z", EventKind.ENTRY, "d1e", "BUY", 100.0)
    day1_exit = _ev("2025-01-10 20:00:00Z", EventKind.EXIT, "d1x", "SELL", 110.0)
    day2_entry = _ev("2025-01-11 14:30:00Z", EventKind.ENTRY, "d2e", "BUY", 100.0)
    day2_exit = _ev("2025-01-11 20:00:00Z", EventKind.EXIT, "d2x", "SELL", 120.0)

    engine = EventEngine(fixed_qty=1.0, slippage_bps=0.0, commission_bps=0.0)

    processed, ledger_rows, final_cash, num_parts = process_daywise(
        engine,
        [day2_entry, day1_exit, day1_entry, day2_exit],  # deliberately shuffled
        market_tz="America/New_York",
        initial_cash=1000.0,
        slippage_bps=0.0,
        commission_bps=0.0,
    )

    assert num_parts == 2
    # Ledger has START + 2 day-end rows
    assert len(ledger_rows) == 3
    # After day1: cash = 1000 -100 +110 = 1010
    assert abs(ledger_rows[1]["cash"] - 1010.0) < 1e-6
    # After day2: cash = 1010 -100 +120 = 1030
    assert abs(final_cash - 1030.0) < 1e-6
    assert abs(ledger_rows[-1]["cash"] - 1030.0) < 1e-6
    # Processed events count equals inputs
    assert len(processed) == 4


def test_determinism_with_shuffled_input():
    events = [
        _ev("2025-01-10 14:30:00Z", EventKind.ENTRY, "e1", "BUY", 100.0),
        _ev("2025-01-10 20:00:00Z", EventKind.EXIT, "x1", "SELL", 110.0),
        _ev("2025-01-11 14:30:00Z", EventKind.ENTRY, "e2", "BUY", 100.0),
        _ev("2025-01-11 20:00:00Z", EventKind.EXIT, "x2", "SELL", 120.0),
    ]

    engine = EventEngine(fixed_qty=1.0, slippage_bps=0.0, commission_bps=0.0)

    _, ledger_a, final_a, _ = process_daywise(engine, events, "America/New_York", 1000.0)

    shuffled = [events[2], events[0], events[3], events[1]]
    engine2 = EventEngine(fixed_qty=1.0, slippage_bps=0.0, commission_bps=0.0)
    _, ledger_b, final_b, _ = process_daywise(engine2, shuffled, "America/New_York", 1000.0)

    assert ledger_a == ledger_b
    assert abs(final_a - final_b) < 1e-9
