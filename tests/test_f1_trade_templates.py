"""
Tests for F1-C1: TradeTemplate Datamodel

Proves:
- Templates are immutable and validated
- Extraction is deterministic
- Shuffle-invariant
- No qty calculation
"""

import pytest
import pandas as pd
from datetime import datetime, timezone

from axiom_bt.trade_templates import TradeTemplate, extract_templates_from_orders


def test_trade_template_creation():
    """F1-C1: TradeTemplate can be created with valid data."""
    template = TradeTemplate(
        template_id="AAPL_20260105_100000_0",
        symbol="AAPL",
        side="BUY",
        entry_ts=pd.Timestamp("2026-01-05 10:00:00", tz="America/New_York"),
        entry_price=150.0,
        entry_reason="inside_bar_long",
    )
    
    assert template.symbol == "AAPL"
    assert template.side == "BUY"
    assert template.entry_price == 150.0
    assert template.is_long == True
    assert template.is_closed == False


def test_trade_template_immutable():
    """F1-C1: TradeTemplate is frozen (immutable)."""
    template = TradeTemplate(
        template_id="test",
        symbol="AAPL",
        side="BUY",
        entry_ts=pd.Timestamp("2026-01-05 10:00:00", tz="America/New_York"),
        entry_price=150.0,
        entry_reason="test",
    )
    
    # Should raise because dataclass is frozen
    with pytest.raises(Exception):  # FrozenInstanceError
        template.entry_price = 160.0


def test_trade_template_validation_negative_price():
    """F1-C1: Template validation rejects negative prices."""
    with pytest.raises(ValueError, match="entry_price must be positive"):
        TradeTemplate(
            template_id="test",
            symbol="AAPL",
            side="BUY",
            entry_ts=pd.Timestamp("2026-01-05 10:00:00"),
            entry_price=-150.0,  # Invalid
            entry_reason="test",
        )


def test_trade_template_validation_exit_before_entry():
    """F1-C1: Template validation rejects exit before entry."""
    with pytest.raises(ValueError, match="entry_ts.*must be before exit_ts"):
        TradeTemplate(
            template_id="test",
            symbol="AAPL",
            side="BUY",
            entry_ts=pd.Timestamp("2026-01-05 10:00:00"),
            entry_price=150.0,
            entry_reason="test",
            exit_ts=pd.Timestamp("2026-01-05 09:00:00"),  # Before entry!
            exit_price=155.0,
        )


def test_extract_templates_deterministic():
    """F1-C1: Extraction produces same templates from same orders (determinism)."""
    orders = pd.DataFrame({
        "entry_ts": [
            pd.Timestamp("2026-01-05 10:00:00"),
            pd.Timestamp("2026-01-05 11:00:00"),
        ],
        "side": ["BUY", "SELL"],
        "entry_price": [150.0, 160.0],
        "reason": ["signal_1", "signal_2"],
        "exit_ts": [None, None],
        "exit_price": [None, None],
        "stop_loss": [145.0, 165.0],
        "take_profit": [155.0, 155.0],
        "atr": [2.5, 2.8],
    })
    
    # Extract twice
    templates1 = extract_templates_from_orders(orders, "AAPL")
    templates2 = extract_templates_from_orders(orders, "AAPL")
    
    # Must be identical
    assert len(templates1) == len(templates2)
    assert len(templates1) == 2
    
    for t1, t2 in zip(templates1, templates2):
        assert t1.template_id == t2.template_id
        assert t1.entry_ts == t2.entry_ts
        assert t1.entry_price == t2.entry_price


def test_extract_templates_shuffle_invariant():
    """F1-C1: Extraction order doesn't depend on input row order (shuffle-invariant)."""
    orders_original = pd.DataFrame({
        "entry_ts": [
            pd.Timestamp("2026-01-05 11:00:00"),  # Later first
            pd.Timestamp("2026-01-05 10:00:00"),  # Earlier second
        ],
        "side": ["SELL", "BUY"],
        "entry_price": [160.0, 150.0],
        "reason": ["signal_2", "signal_1"],
        "exit_ts": [None, None],
        "exit_price": [None, None],
        "stop_loss": [165.0, 145.0],
        "take_profit": [155.0, 155.0],
        "atr": [2.8, 2.5],
    })
    
    # Shuffled version (reversed)
    orders_shuffled = orders_original.iloc[::-1].reset_index(drop=True)
    
    templates1 = extract_templates_from_orders(orders_original, "AAPL")
    templates2 = extract_templates_from_orders(orders_shuffled, "AAPL")
    
    # Results must be IDENTICAL (same order after sorting)
    assert len(templates1) == len(templates2)
    
    # First template should be 10:00 entry (earliest)
    assert templates1[0].entry_ts == pd.Timestamp("2026-01-05 10:00:00")
    assert templates2[0].entry_ts == pd.Timestamp("2026-01-05 10:00:00")
    
    # Second should be 11:00 entry
    assert templates1[1].entry_ts == pd.Timestamp("2026-01-05 11:00:00")
    assert templates2[1].entry_ts == pd.Timestamp("2026-01-05 11:00:00")


def test_template_no_qty_field():
    """F1-C1: Critical - Templates do NOT contain qty (calculated at execution)."""
    template = TradeTemplate(
        template_id="test",
        symbol="AAPL",
        side="BUY",
        entry_ts=pd.Timestamp("2026-01-05 10:00:00"),
        entry_price=150.0,
        entry_reason="test",
    )
    
    # Verify qty is NOT in the dataclass
    assert not hasattr(template, "qty")
    assert not hasattr(template, "quantity")
    assert not hasattr(template, "shares")
    
    # Verify to_dict() doesn't include qty
    dict_repr = template.to_dict()
    assert "qty" not in dict_repr
    assert "quantity" not in dict_repr


def test_template_to_dict_export():
    """F1-C1: Template exports cleanly to dict for debugging/testing."""
    template = TradeTemplate(
        template_id="AAPL_20260105_100000_0",
        symbol="AAPL",
        side="BUY",
        entry_ts=pd.Timestamp("2026-01-05 10:00:00"),
        entry_price=150.0,
        entry_reason="inside_bar_long",
        stop_loss_price=145.0,
        take_profit_price=155.0,
        atr_at_entry=2.5,
    )
    
    result = template.to_dict()
    
    assert result["symbol"] == "AAPL"
    assert result["side"] == "BUY"
    assert result["entry_price"] == 150.0
    assert result["stop_loss_price"] == 145.0
    assert result["is_closed"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
