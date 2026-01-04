"""
Tests for Step B: Replay from Trades (Determinism + Parity).

Tests verify that:
- replay_from_trades() is deterministic (shuffle-invariant)
- Legacy-like equity curve matches metrics.equity_from_trades()
- Required fields are validated
"""

import pytest
import pandas as pd
import numpy as np
from axiom_bt.portfolio.ledger import PortfolioLedger
from axiom_bt.metrics import equity_from_trades


def create_sample_trades_df():
    """Create a sample trades DataFrame for testing."""
    return pd.DataFrame({
        "symbol": ["AAPL", "AAPL", "MSFT", "AAPL", "MSFT"],
        "side": ["BUY", "SELL", "BUY", "BUY", "SELL"],
        "entry_ts": pd.to_datetime([
            "2025-01-01 09:30", "2025-01-01 10:00", "2025-01-01 10:30",
            "2025-01-01 11:00", "2025-01-01 11:30"
        ], utc=True),
        "exit_ts": pd.to_datetime([
            "2025-01-01 10:00", "2025-01-01 11:00", "2025-01-01 12:00",
            "2025-01-01 13:00", "2025-01-01 14:00"
        ], utc=True),
        "entry_price": [150.0, 151.0, 300.0, 152.0, 302.0],
        "exit_price": [151.0, 150.0, 305.0, 153.0, 300.0],
        "qty": [100, 100, 50, 100, 50],
        "pnl": [100.0, -100.0, 250.0, 100.0, -100.0],  # Net PnL
        "fees": [2.0, 2.0, 3.0, 2.0, 3.0],
        "slippage": [0.5, 0.5, 1.0, 0.5, 1.0],
        "reason": ["TP", "SL", "TP", "TP", "SL"]
    })


def test_replay_deterministic_independent_of_row_order():
    """Replay must be deterministic: shuffled trades → same ledger output."""
    initial_cash = 10000.0
    trades = create_sample_trades_df()
    
    # Replay with original order
    ledger1 = PortfolioLedger.replay_from_trades(trades, initial_cash)
    df1 = ledger1.to_frame()
    
    # Shuffle the DataFrame (random row order)
    trades_shuffled = trades.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Replay with shuffled order
    ledger2 = PortfolioLedger.replay_from_trades(trades_shuffled, initial_cash)
    df2 = ledger2.to_frame()
    
    # Results must be identical (deterministic sort)
    pd.testing.assert_frame_equal(df1, df2)
    
    # Final cash must match
    assert ledger1.cash == ledger2.cash


def test_replay_legacy_like_matches_metrics_equity_from_trades():
    """Legacy-like equity curve must match metrics.equity_from_trades() output."""
    initial_cash = 10000.0
    trades = create_sample_trades_df()
    
    # Existing production function
    metrics_equity = equity_from_trades(trades, initial_cash)
    
    # Replay ledger
    ledger = PortfolioLedger.replay_from_trades(trades, initial_cash)
    replay_equity = ledger.to_equity_curve_legacy_like()
    
    # Should have same number of rows (one per trade, no START)
    assert len(replay_equity) == len(metrics_equity)
    
    # Equity values should match (within tolerance)
    np.testing.assert_allclose(
        replay_equity["equity"].values,
        metrics_equity["equity"].values,
        rtol=1e-9,
        atol=1e-9
    )
    
    # Timestamps should match


def test_replay_requires_exit_ts_and_pnl():
    """Replay should raise ValueError if required fields are missing."""
    initial_cash = 10000.0
    
    # Missing exit_ts
    with pytest.raises(ValueError, match="exit_ts"):
        PortfolioLedger.replay_from_trades(
            pd.DataFrame({"pnl": [100]}),
            initial_cash
        )
    
    # Missing pnl
    with pytest.raises(ValueError, match="pnl"):
        PortfolioLedger.replay_from_trades(
            pd.DataFrame({"exit_ts": [pd.Timestamp.now(tz="UTC")]}),
            initial_cash
        )


def test_replay_empty_trades_creates_start_only():
    """Replay with empty trades should create ledger with only START entry."""
    initial_cash = 10000.0
    empty_trades = pd.DataFrame(columns=["exit_ts", "pnl"])
    
    ledger = PortfolioLedger.replay_from_trades(empty_trades, initial_cash)
    
    # Should have only START entry
    assert len(ledger.entries) == 1
    assert ledger.entries[0].event_type == "START"
    assert ledger.cash == initial_cash


def test_replay_handles_missing_optional_fields():
    """Replay should gracefully handle missing optional fields (fees, slippage, etc)."""
    initial_cash = 10000.0
    
    # Minimal DataFrame (only required fields)
    trades = pd.DataFrame({
        "exit_ts": pd.to_datetime(["2025-01-01 10:00", "2025-01-01 11:00"], utc=True),
        "pnl": [100.0, 50.0]
    })
    
    # Should not crash
    ledger = PortfolioLedger.replay_from_trades(trades, initial_cash)
    
    # Should have replayed 2 trades + START
    assert len(ledger.entries) == 3
    assert ledger.cash == initial_cash + 100 + 50


def test_replay_cost_field_mapping_robust():
    """Replay should correctly map fees/slippage from various field names."""
    initial_cash = 10000.0
    
    # Trades with split fee/slippage fields
    trades = pd.DataFrame({
        "exit_ts": pd.to_datetime(["2025-01-01 10:00"], utc=True),
        "pnl": [100.0],
        "fees_entry": [1.0],
        "fees_exit": [1.5],
        "slippage_entry": [0.3],
        "slippage_exit": [0.7]
    })
    
    ledger = PortfolioLedger.replay_from_trades(trades, initial_cash)
    
    # Check that fees/slippage were summed
    trade_entry = ledger.entries[1]  # First trade (0 is START)
    assert trade_entry.fees == 1.0 + 1.5
    assert trade_entry.slippage == 0.3 + 0.7


def test_replay_sort_keys_are_stable():
    """Verify that sort keys produce stable, deterministic ordering."""
    initial_cash = 10000.0
    
    # Create trades with identical exit_ts but different symbols
    trades = pd.DataFrame({
        "symbol": ["MSFT", "AAPL", "GOOGL"],
        "exit_ts": pd.to_datetime(["2025-01-01 10:00"] * 3, utc=True),
        "entry_ts": pd.to_datetime(["2025-01-01 09:30"] * 3, utc=True),
        "side": ["BUY", "BUY", "BUY"],
        "entry_price": [300.0, 150.0, 2800.0],
        "pnl": [50.0, 30.0, 100.0]
    })
    
    # Replay multiple times with shuffle
    ledgers = []
    for seed in [1, 42, 123]:
        shuffled = trades.sample(frac=1, random_state=seed).reset_index(drop=True)
        ledger = PortfolioLedger.replay_from_trades(shuffled, initial_cash)
        ledgers.append(ledger.to_frame())
    
    # All should be identical
    for i in range(1, len(ledgers)):
        pd.testing.assert_frame_equal(ledgers[0], ledgers[i])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
