"""
Simple cache for data availability with TTL.

JUSTIFICATION FOR GLOBAL STATE:
- Avoids repeated filesystem I/O for parquet metadata reads
- TTL prevents stale data (60s is reasonable for quasi-static files)
- Max-size prevents unbounded memory growth
- Single-user dashboard: no cross-user concerns

Performance impact without cache:
- 5 parquet files * ~50ms metadata read = ~250ms per symbol
- With cache: <1ms for cached symbols

Cache TTL: 60 seconds
Max cache size: 100 symbols
"""

import time
from typing import Optional, Dict, Any

# Global cache storage
# Key: symbol, Value: {data: dict, cached_at: float}
_cache: Dict[str, Dict[str, Any]] = {}

# Cache configuration
CACHE_TTL_SECONDS = 60
MAX_CACHE_SIZE = 100


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
    age = time.monotonic() - entry['cached_at']
    
    if age > CACHE_TTL_SECONDS:
        # Expired, remove from cache
        del _cache[symbol]
        return None
    
    return entry['data']


def set_cached(symbol: str, data: Dict[str, Any]) -> None:
    """
    Cache availability data for symbol.
    
    Evicts oldest entry if cache is full.
    
    Args:
        symbol: Stock symbol
        data: Availability data dict
    """
    # Evict oldest if at max size
    if len(_cache) >= MAX_CACHE_SIZE and symbol not in _cache:
        # Find oldest entry
        oldest_symbol = min(_cache.keys(), 
                           key=lambda s: _cache[s]['cached_at'])
        del _cache[oldest_symbol]
    
    _cache[symbol] = {
        'data': data,
        'cached_at': time.monotonic()
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
        Dict with cache size, max size, and oldest entry age
    """
    if not _cache:
        return {
            'size': 0,
            'max_size': MAX_CACHE_SIZE,
            'oldest_age_seconds': 0
        }
    
    now = time.monotonic()
    oldest_age = max(now - entry['cached_at'] 
                     for entry in _cache.values())
    
    return {
        'size': len(_cache),
        'max_size': MAX_CACHE_SIZE,
        'oldest_age_seconds': oldest_age
    }
