"""
Simple cache for data availability with TTL.

Used to avoid repeated filesystem scans when checking data availability.
Cache TTL: 60 seconds
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Global cache storage
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = timedelta(seconds=60)


def get_cached(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get cached availability data for symbol.
    
    Args:
        symbol: Stock symbol
    
    Returns:
        Cached data dict if valid, None if expired or missing
    """
    if symbol not in _cache:
        return None
    
    entry = _cache[symbol]
    if datetime.now() - entry['cached_at'] > CACHE_TTL:
        # Expired, remove from cache
        del _cache[symbol]
        return None
    
    return entry['data']


def set_cached(symbol: str, data: Dict[str, Any]) -> None:
    """
    Cache availability data for symbol.
    
    Args:
        symbol: Stock symbol
        data: Availability data dict
    """
    _cache[symbol] = {
        'data': data,
        'cached_at': datetime.now()
    }


def invalidate(symbol: str) -> None:
    """
    Invalidate cache for specific symbol.
    
    Args:
        symbol: Stock symbol to invalidate
    """
    if symbol in _cache:
        del _cache[symbol]


def clear_all() -> None:
    """Clear entire cache."""
    _cache.clear()


def get_cache_info() -> Dict[str, Any]:
    """
    Get cache statistics.
    
    Returns:
        Dict with cache size and oldest entry age
    """
    if not _cache:
        return {'size': 0, 'oldest_age_seconds': 0}
    
    now = datetime.now()
    oldest_age = max((now - entry['cached_at']).total_seconds() 
                     for entry in _cache.values())
    
    return {
        'size': len(_cache),
        'oldest_age_seconds': oldest_age
    }
