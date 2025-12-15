"""Canonical intraday storage paths - single source of truth.

This module defines the canonical storage locations for intraday data.
All components (IntradayStore, CandleAggregator, Parquet writers) must
use these paths to ensure consistency.
"""

from pathlib import Path
from typing import Dict

# Canonical root
INTRADAY_ROOT = Path("./artifacts")

# Timeframe directories
DATA_M1 = INTRADAY_ROOT / "data_m1"
DATA_M5 = INTRADAY_ROOT / "data_m5"
DATA_M15 = INTRADAY_ROOT / "data_m15"
DATA_D1 = INTRADAY_ROOT / "data_d1"

# Timeframe mapping
TIMEFRAME_PATHS: Dict[str, Path] = {
    "M1": DATA_M1,
    "M5": DATA_M5,
    "M15": DATA_M15,
    "D1": DATA_D1,
}


def get_intraday_parquet_path(symbol: str, timeframe: str) -> Path:
    """Get canonical parquet file path for symbol/timeframe.
    
    Args:
        symbol: Stock symbol (will be normalized to uppercase)
        timeframe: Timeframe string (M1, M5, M15, D1)
        
    Returns:
        Path to parquet file (e.g., artifacts/data_m5/AAPL.parquet)
        
    Raises:
        ValueError: If timeframe is not supported
        
    Example:
        >>> get_intraday_parquet_path("AAPL", "M5")
        PosixPath('artifacts/data_m5/AAPL.parquet')
    """
    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
    
    if timeframe not in TIMEFRAME_PATHS:
        supported = ", ".join(TIMEFRAME_PATHS.keys())
        raise ValueError(f"Unsupported timeframe '{timeframe}'. Supported: {supported}")
    
    base_dir = TIMEFRAME_PATHS[timeframe]
    return base_dir / f"{symbol}.parquet"


def ensure_intraday_layout() -> None:
    """Create canonical intraday directory structure if it doesn't exist."""
    INTRADAY_ROOT.mkdir(parents=True, exist_ok=True)
    
    for path in TIMEFRAME_PATHS.values():
        path.mkdir(parents=True, exist_ok=True)


def get_all_symbols(timeframe: str) -> list[str]:
    """Get list of all symbols with parquet files for given timeframe.
    
    Args:
        timeframe: Timeframe string (M1, M5, M15, D1)
        
    Returns:
        List of symbols (sorted, uppercase)
    """
    if timeframe not in TIMEFRAME_PATHS:
        return []
    
    base_dir = TIMEFRAME_PATHS[timeframe]
    if not base_dir.exists():
        return []
    
    symbols = []
    for file_path in base_dir.glob("*.parquet"):
        symbol = file_path.stem  # Remove .parquet extension
        symbols.append(symbol.upper())
    
    return sorted(symbols)
