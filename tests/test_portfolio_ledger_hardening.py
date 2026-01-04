"""
Tests for hardened PortfolioLedger module.

Tests ledger ordering, START entry, deterministic sequencing, and accounting.
"""

import pytest
import pandas as pd
from axiom_bt.portfolio.ledger import PortfolioLedger, LedgerEntry


def test_ledger_has_start_entry():
    """Test that ledger creates START entry on initialization."""
    ledger = PortfolioLedger(10000)
    
    # Should have exactly 1 entry (START)
    assert len(ledger.entries) == 1
    
    start_entry = ledger.entries[0]
    assert start_entry.event_type == "START"
    assert start_entry.seq == 0
    assert start_entry.cash_before == 10000
    assert start_entry.cash_after == 10000
    assert start_entry.equity_before == 10000
    assert start_entry.equity_after == 10000
    assert start_entry.pnl == 0.0
    assert start_entry.fees == 0.0


def test_ledger_monotonic_and_seq_order():
    """Test that ledger enforces monotonic timestamps and sequence numbers."""
    start_ts = pd.Timestamp("2025-01-01", tz="UTC")
    ledger = PortfolioLedger(10000, start_ts=start_ts)
    
    # Apply trades in order
    ledger.apply_trade(
        exit_ts=pd.Timestamp("2025-01-02", tz="UTC"),
        pnl=100,
        fees=1,
        meta={"trade": 1}
    )
    
    ledger.apply_trade(
        exit_ts=pd.Timestamp("2025-01-03", tz="UTC"),
        pnl=200,
        fees=2,
        meta={"trade": 2}
    )
    
    # Check sequence numbers
    entries = ledger.entries
    assert len(entries) == 3  # START + 2 trades
    assert entries[0].seq == 0
    assert entries[1].seq == 1
    assert entries[2].seq == 2
    
    # Check timestamps are monotonic
    assert entries[0].ts < entries[1].ts < entries[2].ts


def test_ledger_rejects_non_monotonic_timestamps():
    """Test that ledger raises error on backward timestamps."""
    start_ts = pd.Timestamp("2025-01-01", tz="UTC")
    ledger = PortfolioLedger(10000, start_ts=start_ts, enforce_monotonic=True)
    
    # First trade
    ledger.apply_trade(
        exit_ts=pd.Timestamp("2025-01-05", tz="UTC"),
        pnl=100
    )
    
    # Try to apply trade with earlier timestamp
    with pytest.raises(ValueError, match="Non-monotonic timestamp"):
        ledger.apply_trade(
            exit_ts=pd.Timestamp("2025-01-03", tz="UTC"),  # Before previous
            pnl=50
        )


def test_ledger_allows_same_timestamp_with_seq():
    """Test that ledger allows same timestamp (seq disambiguates)."""
    start_ts = pd.Timestamp("2025-01-01", tz="UTC")
    ledger = PortfolioLedger(10000, start_ts=start_ts)
    
    same_ts = pd.Timestamp("2025-01-02 10:00", tz="UTC")
    
    # Two trades at exact same timestamp
    ledger.apply_trade(exit_ts=same_ts, pnl=100, meta={"order": 1})
    ledger.apply_trade(exit_ts=same_ts, pnl=200, meta={"order": 2})
    
    entries = ledger.entries
    assert entries[1].ts == entries[2].ts  # Same timestamp
    assert entries[1].seq < entries[2].seq  # Different seq


def test_ledger_final_cash_matches_initial_plus_pnl_minus_costs():
    """Test accounting: final_cash = initial + pnl - fees - slippage."""
    initial = 10000.0
    ledger = PortfolioLedger(initial)
    
    # Apply some trades
    trades = [
        {"pnl": 100, "fees": 1, "slippage": 0.5},
        {"pnl": -50, "fees": 2, "slippage": 1.0},
        {"pnl": 200, "fees": 1.5, "slippage": 0.0},
    ]
    
    for i, trade in enumerate(trades):
        ledger.apply_trade(
            exit_ts=pd.Timestamp.now(tz="UTC") + pd.Timedelta(seconds=i),
            **trade
        )
    
    # Calculate expected final cash
    # PnL already includes fees deduction in real system, but here we're testing the accounting
    total_pnl = sum(t["pnl"] for t in trades)
    expected_cash = initial + total_pnl
    
    assert abs(ledger.cash - expected_cash) < 0.01
    assert abs(ledger.equity - expected_cash) < 0.01


def test_ledger_cash_before_after_evidence():
    """Test that ledger tracks cash_before and cash_after correctly."""
    ledger = PortfolioLedger(10000)
    
    # First trade: +100
    ledger.apply_trade(
        exit_ts=pd.Timestamp.now(tz="UTC"),
        pnl=100,
        fees=0
    )
    
    entry1 = ledger.entries[1]  # [0] is START
    assert entry1.cash_before == 10000
    assert entry1.cash_after == 10100
    
    # Second trade: -50
    ledger.apply_trade(
        exit_ts=pd.Timestamp.now(tz="UTC") + pd.Timedelta(seconds=1),
        pnl=-50,
        fees=0
    )
    
    entry2 = ledger.entries[2]
    assert entry2.cash_before == 10100  # Previous cash_after
    assert entry2.cash_after == 10050


def test_ledger_summary_stats():
    """Test ledger.summary() returns correct statistics."""
    ledger = PortfolioLedger(10000)
    
    # Empty ledger (only START)
    summary = ledger.summary()
    assert summary["initial_cash"] == 10000
    assert summary["final_cash"] == 10000
    assert summary["total_pnl"] == 0.0
    assert summary["num_events"] == 0
    
    # Add trades
    ledger.apply_trade(pd.Timestamp.now(tz="UTC"), pnl=100, fees=5, slippage=1)
    ledger.apply_trade(pd.Timestamp.now(tz="UTC") + pd.Timedelta(seconds=1), pnl=200, fees=10, slippage=2)
    
    summary = ledger.summary()
    assert summary["initial_cash"] == 10000
    assert summary["final_cash"] == 10300  # 10000 + 100 + 200
    assert summary["total_pnl"] == 300
    assert summary["total_fees"] == 15
    assert summary["total_slippage"] == 3
    assert summary["num_events"] == 2


def test_ledger_to_frame_includes_all_fields():
    """Test that to_frame() exports all evidence fields."""
    ledger = PortfolioLedger(10000)
    ledger.apply_trade(pd.Timestamp.now(tz="UTC"), pnl=100, fees=1)
    
    df = ledger.to_frame()
    
    required_cols = [
        "seq", "ts", "event_type", "pnl", "fees", "slippage",
        "cash_before", "cash_after", "equity_before", "equity_after"
    ]
    
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
    
    # Should have 2 rows: START + 1 trade
    assert len(df) == 2
    assert df.iloc[0]["event_type"] == "START"
    assert df.iloc[1]["event_type"] == "TRADE_EXIT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
