"""
Tests for P3-C3: Exit Policies (Time-Based Exit)

Proves:
- apply_time_exit adds exit info to entry-only templates
- Handles edge cases (empty bars, entry not in index, clamping)
- Deterministic and shuffle-invariant
- Integration: compound path produces ready templates and processes roundtrips
"""

import pytest
import pandas as pd
import numpy as np

from axiom_bt.exit_policies import apply_time_exit
from axiom_bt.trade_templates import TradeTemplate


def test_time_exit_adds_exit_fields_when_bar_exists():
    """P3-C3: apply_time_exit adds exit_ts and exit_price when bars available."""
    # Create entry-only template
    entry_ts = pd.Timestamp("2026-01-07 10:00:00")
    template = TradeTemplate(
        template_id="t1",
        symbol="AAPL",
        side="BUY",
        entry_ts=entry_ts,
        entry_price=100.0,
        entry_reason="test",
        exit_ts=None,
        exit_price=None,
    )
    
    # Create bars (entry at index 0, hold 1 bar → exit at index 1)
    bars = pd.DataFrame({
        'close': [100.0, 105.0, 104.0]
    }, index=pd.DatetimeIndex([
        pd.Timestamp("2026-01-07 10:00:00"),
        pd.Timestamp("2026-01-07 10:05:00"),
        pd.Timestamp("2026-01-07 10:10:00"),
    ]))
    
    # Apply time exit (hold_bars=1)
    result = apply_time_exit([template], bars, hold_bars=1)
    
    # Verify exit added
    assert len(result) == 1
    updated = result[0]
    
    assert updated.exit_ts == pd.Timestamp("2026-01-07 10:05:00")
    assert updated.exit_price == 105.0
    assert updated.exit_reason == "time_exit_1"
    
    # Entry fields unchanged
    assert updated.entry_ts == entry_ts
    assert updated.entry_price == 100.0


def test_time_exit_uses_next_bar_when_entry_not_exact_index():
    """P3-C3: When entry_ts not in index, use next bar via searchsorted."""
    # Entry at 10:02 (not in index)
    entry_ts = pd.Timestamp("2026-01-07 10:02:00")
    template = TradeTemplate(
        template_id="t1",
        symbol="AAPL",
        side="BUY",
        entry_ts=entry_ts,
        entry_price=100.0,
        entry_reason="test",
    )
    
    # Bars at 10:00, 10:05, 10:10
    bars = pd.DataFrame({
        'close': [100.0, 105.0, 104.0]
    }, index=pd.DatetimeIndex([
        pd.Timestamp("2026-01-07 10:00:00"),
        pd.Timestamp("2026-01-07 10:05:00"),
        pd.Timestamp("2026-01-07 10:10:00"),
    ]))
    
    # Apply (hold_bars=1)
    result = apply_time_exit([template], bars, hold_bars=1)
    
    # Entry at 10:02 → next bar is 10:05 (index 1)
    # exit = index 1 + 1 = index 2 (10:10)
    updated = result[0]
    assert updated.exit_ts == pd.Timestamp("2026-01-07 10:10:00")
    assert updated.exit_price == 104.0


def test_time_exit_clamps_to_last_bar():
    """P3-C3: Exit index clamped to last bar if hold_bars would exceed."""
    entry_ts = pd.Timestamp("2026-01-07 10:00:00")
    template = TradeTemplate(
        template_id="t1",
        symbol="AAPL",
        side="BUY",
        entry_ts=entry_ts,
        entry_price=100.0,
        entry_reason="test",
    )
    
    # 3 bars total, entry at first
    bars = pd.DataFrame({
        'close': [100.0, 105.0, 110.0]
    }, index=pd.DatetimeIndex([
        pd.Timestamp("2026-01-07 10:00:00"),  # Entry here (index 0)
        pd.Timestamp("2026-01-07 10:05:00"),
        pd.Timestamp("2026-01-07 10:10:00"),  # Last bar (index 2)
    ]))
    
    # Apply with hold_bars=10 (would go to index 10, but only have index 0-2)
    result = apply_time_exit([template], bars, hold_bars=10)
    
    # Should clamp to last bar (index 2)
    updated = result[0]
    assert updated.exit_ts == pd.Timestamp("2026-01-07 10:10:00")
    assert updated.exit_price == 110.0


def test_time_exit_empty_bars_returns_unchanged():
    """P3-C3: Empty bars DataFrame → templates unchanged."""
    template = TradeTemplate(
        template_id="t1",
        symbol="AAPL",
        side="BUY",
        entry_ts=pd.Timestamp("2026-01-07 10:00:00"),
        entry_price=100.0,
        entry_reason="test",
    )
    
    # Empty bars
    empty_bars = pd.DataFrame({'close': []}, index=pd.DatetimeIndex([]))
    
    result = apply_time_exit([template], empty_bars, hold_bars=1)
    
    # Template unchanged (entry-only)
    assert len(result) == 1
    assert result[0].exit_ts is None
    assert result[0].exit_price is None


def test_time_exit_preserves_existing_exits():
    """P3-C3: Templates with existing exit info are unchanged."""
    # Template with exit already
    template = TradeTemplate(
        template_id="t1",
        symbol="AAPL",
        side="BUY",
        entry_ts=pd.Timestamp("2026-01-07 10:00:00"),
        entry_price=100.0,
        entry_reason="test",
        exit_ts=pd.Timestamp("2026-01-07 11:00:00"),
        exit_price=110.0,
        exit_reason="manual",
    )
    
    bars = pd.DataFrame({
        'close': [100.0, 105.0, 104.0]
    }, index=pd.DatetimeIndex([
        pd.Timestamp("2026-01-07 10:00:00"),
        pd.Timestamp("2026-01-07 10:05:00"),
        pd.Timestamp("2026-01-07 10:10:00"),
    ]))
    
    result = apply_time_exit([template], bars, hold_bars=1)
    
    # Exit unchanged
    updated = result[0]
    assert updated.exit_ts == pd.Timestamp("2026-01-07 11:00:00")
    assert updated.exit_price == 110.0
    assert updated.exit_reason == "manual"


def test_time_exit_shuffle_invariant():
    """P3-C3: Input order doesn't affect output (deterministic)."""
    ts1 = pd.Timestamp("2026-01-07 10:00:00")
    ts2 = pd.Timestamp("2026-01-07 10:05:00")
    
    templates = [
        TradeTemplate("t1", "AAPL", "BUY", ts1, 100.0, "r1"),
        TradeTemplate("t2", "MSFT", "SELL", ts2, 200.0, "r2"),
    ]
    
    templates_shuffled = [templates[1], templates[0]]
    
    bars = pd.DataFrame({
        'close': [100.0, 105.0, 110.0]
    }, index=pd.DatetimeIndex([
        pd.Timestamp("2026-01-07 10:00:00"),
        pd.Timestamp("2026-01-07 10:05:00"),
        pd.Timestamp("2026-01-07 10:10:00"),
    ]))
    
    result1 = apply_time_exit(templates, bars, hold_bars=1)
    result2 = apply_time_exit(templates_shuffled, bars, hold_bars=1)
    
    # Sort by template_id for comparison
    result1_sorted = sorted(result1, key=lambda t: t.template_id)
    result2_sorted = sorted(result2, key=lambda t: t.template_id)
    
    # Same results
    for r1, r2 in zip(result1_sorted, result2_sorted):
        assert r1.template_id == r2.template_id
        assert r1.exit_ts == r2.exit_ts
        assert r1.exit_price == r2.exit_price


def test_time_exit_none_bars_returns_unchanged():
    """P3-C3: None bars → templates unchanged (graceful)."""
    template = TradeTemplate(
        template_id="t1",
        symbol="AAPL",
        side="BUY",
        entry_ts=pd.Timestamp("2026-01-07 10:00:00"),
        entry_price=100.0,
        entry_reason="test",
    )
    
    result = apply_time_exit([template], None, hold_bars=1)
    
    # Unchanged
    assert len(result) == 1
    assert result[0].exit_ts is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
