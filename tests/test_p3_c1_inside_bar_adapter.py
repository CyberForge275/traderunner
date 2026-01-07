"""
Tests for P3-C1a: InsideBar → TradeTemplates Adapter

Proves:
- Deterministic template_id generation
- Correct field mapping (symbol, side, ts, prices)
- Shuffle-invariant output
- Handles empty input
- Validates missing/invalid fields
- Works with both object and dict inputs
"""

import pytest
import pandas as pd
import hashlib

from axiom_bt.strategy_adapters.inside_bar_to_templates import inside_bar_to_trade_templates
from axiom_bt.trade_templates import TradeTemplate


# Mock RawSignal-like object for testing
class MockSignal:
    def __init__(self, timestamp, side, entry_price, symbol="TEST", metadata=None):
        self.timestamp = timestamp
        self.side = side
        self.entry_price = entry_price
        self.symbol = symbol
        self.metadata = metadata or {}


def test_deterministic_template_id():
    """P3-C1a: Same signal → same template_id (deterministic)."""
    ts = pd.Timestamp("2026-01-07 10:00:00")
    
    signal1 = MockSignal(ts, "BUY", 100.0, "AAPL")
    signal2 = MockSignal(ts, "BUY", 100.0, "AAPL")  # Identical
    
    templates1 = inside_bar_to_trade_templates([signal1])
    templates2 = inside_bar_to_trade_templates([signal2])
    
    assert len(templates1) == 1
    assert len(templates2) == 1
    
    # Same template_id
    assert templates1[0].template_id == templates2[0].template_id
    
    # Verify it's a hash-based ID
    assert templates1[0].template_id.startswith("ib_")
    assert len(templates1[0].template_id) == 15  # "ib_" + 12 hex chars


def test_mapping_fields_entry_only():
    """P3-C1a: Fields mapped correctly (symbol, side, ts, entry_price)."""
    ts = pd.Timestamp("2026-01-07 10:00:00")
    
    signal = MockSignal(ts, "BUY", 150.75, "MSFT", metadata={'entry_reason': 'test'})
    
    templates = inside_bar_to_trade_templates([signal])
    
    assert len(templates) == 1
    template = templates[0]
    
    # Check all fields
    assert template.symbol == "MSFT"
    assert template.side == "BUY"
    assert template.entry_ts == ts
    assert template.entry_price == 150.75
    assert template.entry_reason == "test"
    
    # Exit fields should be None (signals don't have exit info)
    assert template.exit_ts is None
    assert template.exit_price is None
    assert template.exit_reason is None


def test_shuffle_invariant_output_order():
    """P3-C1a: Input shuffled → same output order (deterministic sort)."""
    ts1 = pd.Timestamp("2026-01-07 10:00:00")
    ts2 = pd.Timestamp("2026-01-07 11:00:00")
    
    signals_ordered = [
        MockSignal(ts1, "BUY", 100.0, "AAPL"),
        MockSignal(ts2, "SELL", 200.0, "MSFT"),
    ]
    
    signals_shuffled = [
        MockSignal(ts2, "SELL", 200.0, "MSFT"),  # Reversed
        MockSignal(ts1, "BUY", 100.0, "AAPL"),
    ]
    
    templates1 = inside_bar_to_trade_templates(signals_ordered)
    templates2 = inside_bar_to_trade_templates(signals_shuffled)
    
    # Same length
    assert len(templates1) == len(templates2) == 2
    
    # Same order and IDs
    for t1, t2 in zip(templates1, templates2):
        assert t1.template_id == t2.template_id
        assert t1.symbol == t2.symbol
        assert t1.entry_ts == t2.entry_ts
        assert t1.side == t2.side


def test_missing_entry_price_raises():
    """P3-C1a: ValueError if entry_price missing or <= 0."""
    ts = pd.Timestamp("2026-01-07 10:00:00")
    
    # Missing price
    signal_bad = MockSignal(ts, "BUY", None, "AAPL")
    
    with pytest.raises(ValueError, match="missing or invalid entry_price"):
        inside_bar_to_trade_templates([signal_bad])
    
    # Zero price
    signal_bad2 = MockSignal(ts, "BUY", 0.0, "AAPL")
    
    with pytest.raises(ValueError, match="missing or invalid entry_price"):
        inside_bar_to_trade_templates([signal_bad2])


def test_invalid_side_raises():
    """P3-C1a: ValueError if side invalid."""
    ts = pd.Timestamp("2026-01-07 10:00:00")
    
    signal_bad = MockSignal(ts, "INVALID", 100.0, "AAPL")
    
    with pytest.raises(ValueError, match="Invalid side"):
        inside_bar_to_trade_templates([signal_bad])


def test_empty_signals_returns_empty_list():
    """P3-C1a: Empty input → empty output (valid)."""
    templates = inside_bar_to_trade_templates([])
    assert templates == []
    
    templates_none = inside_bar_to_trade_templates(None)
    assert templates_none == []


def test_dict_input_with_aliases():
    """P3-C1a: Works with dict input and field aliases."""
    ts = pd.Timestamp("2026-01-07 10:00:00")
    
    # Dict with various aliases
    signal_dict = {
        'entry_time': ts,
        'direction': 'LONG',  # Alias for side
        'entry': 100.0,  # Alias for entry_price
        'ticker': 'AAPL',  # Alias for symbol
    }
    
    templates = inside_bar_to_trade_templates([signal_dict])
    
    assert len(templates) == 1
    template = templates[0]
    
    assert template.symbol == "AAPL"
    assert template.side == "BUY"  # LONG → BUY
    assert template.entry_ts == ts
    assert template.entry_price == 100.0


def test_side_normalization():
    """P3-C1a: Side aliases normalized (LONG→BUY, SHORT→SELL)."""
    ts = pd.Timestamp("2026-01-07 10:00:00")
    
    test_cases = [
        ("BUY", "BUY"),
        ("LONG", "BUY"),
        ("1", "BUY"),
        ("+1", "BUY"),
        ("SELL", "SELL"),
        ("SHORT", "SELL"),
        ("-1", "SELL"),
    ]
    
    for input_side, expected_side in test_cases:
        signal = {'timestamp': ts, 'side': input_side, 'entry_price': 100.0, 'symbol': 'TEST'}
        templates = inside_bar_to_trade_templates([signal])
        assert templates[0].side == expected_side, f"Failed for {input_side}"


def test_missing_timestamp_raises():
    """P3-C1a: ValueError if timestamp missing."""
    signal_dict = {
        'side': 'BUY',
        'entry_price': 100.0,
        'symbol': 'AAPL',
        # Missing timestamp
    }
    
    with pytest.raises(ValueError, match="missing timestamp"):
        inside_bar_to_trade_templates([signal_dict])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
