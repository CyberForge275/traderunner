"""Regression test for normalize_session_filter API compatibility.

Ensures that normalize_session_filter function remains available and
backward-compatible for historical callers.

This test prevents ImportError regression from occurring again.
"""

import pytest


def test_normalize_session_filter_import():
    """Verify normalize_session_filter can be imported (regression prevention)."""
    from axiom_bt.data.session_filter import normalize_session_filter
    
    assert callable(normalize_session_filter)


def test_normalize_session_filter_none():
    """normalize_session_filter returns None when input is None."""
    from axiom_bt.data.session_filter import normalize_session_filter
    
    result = normalize_session_filter(None)
    assert result is None


def test_normalize_session_filter_dict_passthrough():
    """normalize_session_filter returns dict as-is when input is already dict."""
    from axiom_bt.data.session_filter import normalize_session_filter
    
    input_dict = {"windows": ["15:00-16:00", "16:00-17:00"]}
    result = normalize_session_filter(input_dict)
    
    assert result == input_dict
    assert result is input_dict  # Same object


def test_normalize_session_filter_list_to_dict():
    """normalize_session_filter wraps list in {windows: list} format."""
    from axiom_bt.data.session_filter import normalize_session_filter
    
    input_list = ["15:00-16:00", "16:00-17:00"]
    result = normalize_session_filter(input_list)
    
    assert result == {"windows": input_list}
    assert isinstance(result, dict)
    assert result["windows"] is input_list


def test_normalize_session_filter_empty_list():
    """normalize_session_filter handles empty list correctly."""
    from axiom_bt.data.session_filter import normalize_session_filter
    
    result = normalize_session_filter([])
    
    assert result == {"windows": []}


def test_normalize_session_filter_defensive_unknown_type():
    """normalize_session_filter handles unexpected types defensively."""
    from axiom_bt.data.session_filter import normalize_session_filter
    
    # Should not crash, returns as-is with warning
    result = normalize_session_filter("unexpected_string")
    
    assert result == "unexpected_string"
