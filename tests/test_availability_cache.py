"""
Tests for availability cache.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from trading_dashboard.utils.availability_cache import (
    get_cached,
    set_cached,
    invalidate,
    clear_all,
    get_cache_info,
    CACHE_TTL,
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


def test_availability_cache_ttl():
    """Test that cache expires after TTL."""
    clear_all()
    
    symbol = "TEST"
    data = {"M5": {"available": True}}
    
    set_cached(symbol, data)
    
    # Should retrieve immediately
    assert get_cached(symbol) == data
    
    # Mock time passing (61 seconds)
    with patch('trading_dashboard.utils.availability_cache.datetime') as mock_dt:
        # Future time
        future_time = datetime.now() + timedelta(seconds=61)
        mock_dt.now.return_value = future_time
        
        # Cache entry was created in the past
        # When get_cached checks, it compares against mocked now()
        # But our cached_at is real datetime.now() from before
        # So we need to verify the logic differently
        
        # Actually test by directly checking the cache expiration
        # Better: set a cache entry with manual cached_at in the past
        from trading_dashboard.utils import availability_cache
        availability_cache._cache[symbol] = {
            'data': data,
            'cached_at': datetime.now() - timedelta(seconds=61)
        }
        
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
    assert info['oldest_age_seconds'] == 0
    
    # Add entry
    set_cached("TEST", {"data": 1})
    
    info = get_cache_info()
    assert info['size'] == 1
    assert info['oldest_age_seconds'] >= 0
    assert info['oldest_age_seconds'] < 5  # Should be very recent


def test_cache_per_symbol():
    """Test that different symbols have separate cache entries."""
    clear_all()
    
    set_cached("AMZN", {"M5": {"available": True}})
    set_cached("AAPL", {"M5": {"available": False}})
    
    assert get_cached("AMZN")["M5"]["available"] is True
    assert get_cached("AAPL")["M5"]["available"] is False
