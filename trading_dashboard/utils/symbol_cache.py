"""Utility to scan cached parquet files and return available symbols."""

from pathlib import Path
from typing import List, Dict, Set


def get_cached_symbols(artifacts_dir: str = None) -> Dict[str, List[str]]:
    """Scan artifacts directory for cached symbol data.

    Args:
        artifacts_dir: Path to artifacts directory (defaults to standard location)

    Returns:
        Dictionary mapping timeframe to list of symbols
        Example: {"M5": ["AAPL", "TSLA", ...], "M1": [...], "D1": [...]}
    """
    if artifacts_dir is None:
        artifacts_dir = Path(__file__).parents[2] / "artifacts"
    else:
        artifacts_dir = Path(artifacts_dir)

    cached_symbols = {}

    # Scan common timeframe directories
    timeframe_dirs = {
        "M1": "data_m1",
        "M5": "data_m5",
        "M15": "data_m15",
        "H1": "data_h1",
        "D1": "data_d1",
    }

    for timeframe, dir_name in timeframe_dirs.items():
        tf_dir = artifacts_dir / dir_name
        if not tf_dir.exists():
            continue

        symbols = []
        for parquet_file in tf_dir.glob("*.parquet"):
            # Extract symbol from filename (e.g., "AAPL.parquet" -> "AAPL")
            symbol = parquet_file.stem
            symbols.append(symbol)

        if symbols:
            cached_symbols[timeframe] = sorted(symbols)

    return cached_symbols


def get_symbols_for_timeframe(timeframe: str, artifacts_dir: str = None) -> List[str]:
    """Get cached symbols for a specific timeframe.

    Args:
        timeframe: Timeframe code (e.g., "M5", "M1", "D1")
        artifacts_dir: Path to artifacts directory

    Returns:
        Sorted list of symbol names
    """
    all_cached = get_cached_symbols(artifacts_dir)
    return all_cached.get(timeframe, [])


def get_all_cached_symbols(artifacts_dir: str = None) -> List[str]:
    """Get all unique symbols across all timeframes.

    Args:
        artifacts_dir: Path to artifacts directory

    Returns:
        Sorted list of unique symbol names
    """
    all_cached = get_cached_symbols(artifacts_dir)
    all_symbols: Set[str] = set()

    for symbols_list in all_cached.values():
        all_symbols.update(symbols_list)

    return sorted(all_symbols)
