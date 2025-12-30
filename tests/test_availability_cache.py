"""
Tests for availability cache with monotonic time.
"""

import pytest
import time

from trading_dashboard.utils.availability_cache import (
    get_cached,
    set_cached,
    invalidate,
    clear_all,
    get_cache_info,
    CACHE_TTL_SECONDS,
    MAX_CACHE_SIZE,
)


def test_availability_cache_set_and_get():
    """Test basic cache set and get."""
    clear_all()

    symbol = "TEST"
    data = {"M5": {"available": True, "rows": 100}}

    # Initially empty
    assert get_cached(symbol) is None

    # Set cache
    set_cached(symbol, data)

    # Should retrieve
    assert get_cached(symbol) == data


def test_availability_cache_ttl(monkeypatch):
    """Test that cache expires after TTL using monotonic time."""
    clear_all()

    symbol = "TEST"
    data = {"M5": {"available": True}}

    # Mock monotonic to control time
    current_time = [1000.0]  # Use list to allow modification in closure

    def mock_monotonic():
        return current_time[0]

    monkeypatch.setattr(time, 'monotonic', mock_monotonic)

    set_cached(symbol, data)

    # Should retrieve immediately
    assert get_cached(symbol) == data

    # Advance time by 61 seconds
    current_time[0] = 1061.0

    # Cache should be expired
    assert get_cached(symbol) is None


def test_availability_cache_invalidation():
    """Test manual cache invalidation."""
    clear_all()

    symbol = "TEST"
    data = {"M5": {"available": True}}

    set_cached(symbol, data)
    assert get_cached(symbol) == data

    # Invalidate
    invalidate(symbol)
    assert get_cached(symbol) is None


def test_clear_all_cache():
    """Test clearing entire cache."""
    clear_all()

    set_cached("TEST1", {"data": 1})
    set_cached("TEST2", {"data": 2})

    assert get_cached("TEST1") is not None
    assert get_cached("TEST2") is not None

    clear_all()

    assert get_cached("TEST1") is None
    assert get_cached("TEST2") is None


def test_get_cache_info():
    """Test cache statistics."""
    clear_all()

    # Empty cache
    info = get_cache_info()
    assert info['size'] == 0
    assert info['max_size'] == MAX_CACHE_SIZE
    assert info['oldest_age_seconds'] == 0

    # Add entry
    set_cached("TEST", {"data": 1})

    info = get_cache_info()
    assert info['size'] == 1
    assert info['max_size'] == MAX_CACHE_SIZE
    assert info['oldest_age_seconds'] >= 0
    assert info['oldest_age_seconds'] < 5  # Should be very recent


def test_cache_per_symbol():
    """Test that different symbols have separate cache entries."""
    clear_all()

    set_cached("AMZN", {"M5": {"available": True}})
    set_cached("AAPL", {"M5": {"available": False}})

    assert get_cached("AMZN")["M5"]["available"] is True
    assert get_cached("AAPL")["M5"]["available"] is False


def test_cache_max_size_eviction(monkeypatch):
    """Test that cache evicts oldest entry when at max size."""
    clear_all()

    # Mock monotonic to control time
    current_time = [1000.0]

    def mock_monotonic():
        current_time[0] += 1  # Each call advances time by 1 second
        return current_time[0]

    monkeypatch.setattr(time, 'monotonic', mock_monotonic)

    # Fill cache to max
    for i in range(MAX_CACHE_SIZE):
        set_cached(f"SYM{i}", {"data": i})

    assert get_cache_info()['size'] == MAX_CACHE_SIZE

    # Add one more - should evict oldest (SYM0)
    set_cached("NEW", {"data": "new"})

    assert get_cache_info()['size'] == MAX_CACHE_SIZE
    assert get_cached("NEW") is not None
    # Oldest should be evicted
    assert get_cached("SYM0") is None
