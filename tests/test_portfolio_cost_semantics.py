"""
Tests for Step C: Cost Semantics Clarification.

Tests verify that:
- pnl is net cash delta (fees already deducted)
- fees/slippage are evidence-only (no double-counting)
- Report fields use standardized _usd naming
"""

import pytest
import pandas as pd
from axiom_bt.portfolio.ledger import PortfolioLedger


def test_cost_semantics_no_double_counting():
    """
    Verify that final_cash = initial_cash + sum(pnl_net_usd).
    
    Fees/slippage must NOT be deducted again (they're evidence-only).
    """
    initial_cash = 10000.0
    ledger = PortfolioLedger(initial_cash, enforce_monotonic=False)
    
    # Apply 3 trades with fees and slippage
    trades = [
        {"ts": "2025-01-01 10:00", "pnl": 100, "fees": 2, "slippage": 0.5},
        {"ts": "2025-01-01 11:00", "pnl": -50, "fees": 2, "slippage": 0.5},
        {"ts": "2025-01-01 12:00", "pnl": 75, "fees": 2, "slippage": 0.5},
    ]
    
    for trade in trades:
        ledger.apply_trade(
            exit_ts=pd.Timestamp(trade["ts"], tz="UTC"),
            pnl=trade["pnl"],
            fees=trade["fees"],
            slippage=trade["slippage"]
        )
    
    # Get summary
    summary = ledger.summary()
    
    # Critical assertion: NO double-counting
    # final_cash should equal initial + sum(pnl) WITHOUT deducting fees/slippage again
    expected_final = initial_cash + sum(t["pnl"] for t in trades)
    assert abs(ledger.cash - expected_final) < 1e-9
    assert abs(summary["final_cash_usd"] - expected_final) < 1e-9
    
    # Fees/slippage are evidence values (totals for audit)
    expected_fees = sum(t["fees"] for t in trades)
    expected_slippage = sum(t["slippage"] for t in trades)
    assert abs(summary["total_fees_usd"] - expected_fees) < 1e-9
    assert abs(summary["total_slippage_usd"] - expected_slippage) < 1e-9
    
    # Total PnL (net) should equal sum of trade PnLs
    expected_pnl_net = sum(t["pnl"] for t in trades)
    assert abs(summary["total_pnl_net_usd"] - expected_pnl_net) < 1e-9


def test_report_fields_use_usd_suffix():
    """Verify that summary fields use standardized _usd naming."""
    ledger = PortfolioLedger(10000, enforce_monotonic=False)
    ledger.apply_trade(
        exit_ts=pd.Timestamp("2025-01-01 10:00", tz="UTC"),
        pnl=100,
        fees=2,
        slippage=0.5
    )
    
    summary = ledger.summary()
    
    # All cash/equity fields should have _usd suffix
    required_fields = [
        "initial_cash_usd",
        "final_cash_usd",
        "total_pnl_net_usd",
        "total_fees_usd",
        "total_slippage_usd",
        "peak_equity_usd"
    ]
    
    for field in required_fields:
        assert field in summary, f"Missing standardized field: {field}"


def test_pnl_is_net_cash_delta():
    """
    Verify that pnl directly affects cash (net semantics).
    
    If pnl includes costs, then cash += pnl should be sufficient.
    """
    ledger = PortfolioLedger(10000, enforce_monotonic=False)
    
    # Trade with net PnL = 100 (already includes fees/slippage in calculation)
    ledger.apply_trade(
        exit_ts=pd.Timestamp("2025-01-01 10:00", tz="UTC"),
        pnl=100,  # Net PnL (post-costs)
        fees=5,    # Evidence
        slippage=2  # Evidence
    )
    
    # Cash should increase by exactly 100 (not 100-5-2)
    assert ledger.cash == 10100
    
    # Fees/slippage are separate evidence (not re-applied)
    summary = ledger.summary()
    assert summary["total_fees_usd"] == 5
    assert summary["total_slippage_usd"] == 2
    assert summary["total_pnl_net_usd"] == 100


def test_formula_cash_after_equals_cash_before_plus_pnl_net():
    """Verify the core formula: cash_after = cash_before + pnl_net."""
    ledger = PortfolioLedger(10000, enforce_monotonic=False)
    
    cash_before = ledger.cash
    pnl_net = 123.45
    
    ledger.apply_trade(
        exit_ts=pd.Timestamp("2025-01-01 10:00", tz="UTC"),
        pnl=pnl_net,
        fees=10,  # Evidence only
        slippage=5  # Evidence only
    )
    
    cash_after = ledger.cash
    
    # Core formula holds
    assert abs(cash_after - (cash_before + pnl_net)) < 1e-9
    
    # Check ledger entry evidence
    trade_entry = ledger.entries[1]  # 0 is START
    assert abs(trade_entry.cash_before - cash_before) < 1e-9
    assert abs(trade_entry.cash_after - cash_after) < 1e-9
    assert abs(trade_entry.pnl - pnl_net) < 1e-9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
