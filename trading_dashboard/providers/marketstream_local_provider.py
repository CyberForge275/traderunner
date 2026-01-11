"""marketstream_local Provider - S2a (Full-Load only, Parquet read).

Reads OHLCV data from local parquet files in MARKETDATA_DATA_ROOT.
This is a disk-only provider - no HTTP/async, no window loads, no warmup.

Usage requires:
  - MARKETDATA_DATA_ROOT environment variable set
  - Parquet files in structure: {data_root}/eodhd_http/{timeframe}/{symbol}_{session_mode}.parquet

Restrictions (S2a scope):
  - Full-Load only (start/end must be None)
  - Warmup not supported (raises if warmup_bars set)
  - Session mode defaults to 'rth' if None in request
"""

import os
import pandas as pd
from pathlib import Path
from typing import Tuple

from trading_dashboard.providers.ohlcv_contract import OhlcvProvider, OhlcvRequest


class MarketstreamLocalProvider(OhlcvProvider):
    """Local parquet provider for Full-Load scenarios (S2a)."""
    
    def __init__(self, data_root: str | None = None):
        """Initialize provider with data root path.
        
        Args:
            data_root: Path to MARKETDATA_DATA_ROOT. If None, reads from ENV.
        
        Raises:
            ValueError: If MARKETDATA_DATA_ROOT not set and data_root not provided.
        """
        self.data_root = Path(data_root) if data_root else self._get_data_root_from_env()
        self.provider_id = "marketstream_local"
    
    def _get_data_root_from_env(self) -> Path:
        """Get MARKETDATA_DATA_ROOT from environment."""
        data_root_str = os.getenv("MARKETDATA_DATA_ROOT")
        if not data_root_str:
            raise ValueError(
                "MARKETDATA_DATA_ROOT environment variable not set. "
                "This provider requires a local data root path."
            )
        return Path(data_root_str)
    
    def get_ohlcv(self, request: OhlcvRequest) -> Tuple[pd.DataFrame, dict]:
        """Get OHLCV data from local parquet file (Full-Load only).
        
        Args:
            request: OhlcvRequest with symbol, timeframe, and optional tz
        
        Returns:
            Tuple of (DataFrame, metadata dict)
        
        Raises:
            ValueError: If Window-Load requested (start/end set)
            FileNotFoundError: If parquet file doesn't exist
        """
        # Validate request
        request.validate()
        
        # S2a restriction: Full-Load only
        if request.start is not None or request.end is not None:
            raise ValueError(
                "Window-load not supported in S2a. "
                "For Full-Load, set start=None and end=None."
            )
        
        # Default session_mode to 'rth' if not specified
        session_mode = request.session_mode or "rth"
        
        # Normalize timeframe to lowercase (eodhd convention: m5, not M5)
        timeframe = request.timeframe.lower()
        
        # Build parquet path: {data_root}/eodhd_http/{timeframe}/{symbol}_{session_mode}.parquet
        parquet_path = (
            self.data_root 
            / "eodhd_http" 
            / timeframe 
            / f"{request.symbol}_{session_mode}.parquet"
        )
        
        # Check file exists
        if not parquet_path.exists():
            raise FileNotFoundError(
                f"Parquet file not found: {parquet_path}\\n"
                f"Expected structure: {{MARKETDATA_DATA_ROOT}}/eodhd_http/{{timeframe}}/{{symbol}}_{{session_mode}}.parquet"
            )
        
        # Read parquet
        df = pd.read_parquet(parquet_path)
        
        # Apply TZ conversion if requested
        if request.tz and df.index.tz:
            df.index = df.index.tz_convert(request.tz)
        
        # Build metadata
        metadata = {
            "provider_id": self.provider_id,
            "source": "local_parquet",
            "path": str(parquet_path),
            "symbol": request.symbol,
            "timeframe": timeframe,
            "session_mode": session_mode,
            "row_count": len(df),
            "tz": str(df.index.tz) if df.index.tz else None,
        }
        
        return df, metadata
