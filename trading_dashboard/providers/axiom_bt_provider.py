"""AxiomBT Provider - Adapter to axiom_bt.intraday.IntradayStore.

This adapter wraps the existing IntradayStore to provide the OhlcvProvider interface.

CRITICAL: Preserves existing IntradayStore.load() behavior:
- tz: Optional[str] = None (provider default)
- session_mode: str = "rth" (provider default)

The adapter only passes parameters that were explicitly set in the request to avoid
changing existing behavior.
"""

from __future__ import annotations

from typing import Tuple
import pandas as pd

from axiom_bt.intraday import IntradayStore, Timeframe
from .ohlcv_contract import OhlcvRequest, OhlcvMeta


class AxiomBtProvider:
    """Adapter to axiom_bt.intraday.IntradayStore.
    
    Wraps IntradayStore.load() to provide OhlcvProvider interface while preserving
    existing behavior.
    """
    
    def __init__(self):
        """Initialize with IntradayStore instance."""
        self.intraday_store = IntradayStore()
    
    def get_ohlcv(self, req: OhlcvRequest) -> Tuple[pd.DataFrame, OhlcvMeta]:
        """Get OHLCV data from IntradayStore.
        
        Args:
            req: OhlcvRequest (will be validated)
        
        Returns:
            Tuple of (DataFrame, OhlcvMeta)
        
        Raises:
            ValueError: If request validation fails
            FileNotFoundError: If parquet file not found
        """
        # FIRST: Validate request
        req.validate()
        
        # THEN: Delegate to IntradayStore.load()
        # NOTE: IntradayStore.load() signature:
        #   load(symbol, *, timeframe, tz=None, session_mode="rth")
        # We only pass parameters that were explicitly set in req to preserve behavior
        
        # Normalize timeframe to uppercase for Timeframe enum
        tf = Timeframe[req.timeframe.upper()]
        
        kwargs = {"timeframe": tf}
        if req.tz is not None:
            kwargs["tz"] = req.tz
        if req.session_mode is not None:
            kwargs["session_mode"] = req.session_mode
        
        df = self.intraday_store.load(req.symbol, **kwargs)
        
        meta = OhlcvMeta(
            provider_id="axiom_bt",
            source_effective="IntradayStore",
            row_count_total=len(df),
            warnings=[]
        )
        
        return df, meta
