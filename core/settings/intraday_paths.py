"""Canonical intraday storage paths - single source of truth.

This module defines the canonical storage locations for intraday data using
settings from src.core.settings. All components (IntradayStore, ParquetWriter)
MUST use these paths to ensure consistency.

CRITICAL: No hardcoded paths! All paths derived from settings.
"""

from pathlib import Path
from typing import Dict

# Import canonical settings
from src.settings import ARTIFACTS_ROOT, DATA_M1_DIR, DATA_M5_DIR, DATA_M15_DIR, DATA_D1_DIR, ensure_artifact_layout

# Export for convenience (but derived from settings!)
INTRADAY_ROOT = ARTIFACTS_ROOT
DATA_M1 = DATA_M1_DIR
DATA_M5 = DATA_M5_DIR
DATA_M15 = DATA_M15_DIR
DATA_D1 = DATA_D1_DIR

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
        Absolute path to parquet file (e.g., /opt/trading/traderunner/artifacts/data_m5/AAPL.parquet)
        
    Raises:
        ValueError: If timeframe is not supported
        
    Example:
        >>> get_intraday_parquet_path("AAPL", "M5")
        PosixPath('/opt/trading/traderunner/artifacts/data_m5/AAPL.parquet')
    """
    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
    
    if timeframe not in TIMEFRAME_PATHS:
        supported = ", ".join(TIMEFRAME_PATHS.keys())
        raise ValueError(f"Unsupported timeframe '{timeframe}'. Supported: {supported}")
    
    base_dir = TIMEFRAME_PATHS[timeframe]
    return base_dir / f"{symbol}.parquet"


def ensure_intraday_dirs_exist() -> None:
    """Create canonical intraday directory structure if it doesn't exist.
    
    Uses ensure_artifact_layout from settings to create all directories.
    """
    ensure_artifact_layout()


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
