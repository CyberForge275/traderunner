"""Candle buffer manager for InsideBar strategy."""
from collections import deque
from typing import Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class BufferManager:
    """Manage rolling window of candles for strategy."""
    
    def __init__(self, required_lookback: int = 50):
        """
        Initialize buffer manager.
        
        Args:
            required_lookback: Number of candles to maintain
        """
        self.required_lookback = required_lookback
        self.buffer = deque(maxlen=required_lookback)
        self._initialized = False
    
    def initialize(self, candles: pd.DataFrame):
        """
        Initialize buffer with historical candles.
        
        Args:
            candles: DataFrame with historical candles (sorted oldest→newest)
        """
        if len(candles) < self.required_lookback:
            logger.warning(
                f"Initializing with {len(candles)}/{self.required_lookback} candles"
            )
        
        # Clear and populate
        self.buffer.clear()
        for _, row in candles.iterrows():
            self.buffer.append(row.to_dict())
        
        self._initialized = True
        logger.info(f"✅ Buffer initialized with {len(self.buffer)} candles")
    
    def add_candle(self, candle: dict):
        """Add new candle to buffer (auto-maintains max size)."""
        self.buffer.append(candle)
    
    def get_buffer(self) -> pd.DataFrame:
        """Get current buffer as DataFrame."""
        return pd.DataFrame(list(self.buffer))
    
    def is_ready(self) -> bool:
        """Check if buffer has sufficient data."""
        return self._initialized and len(self.buffer) >= self.required_lookback
    
    def get_readiness_status(self) -> dict:
        """Get detailed readiness status."""
        return {
            'initialized': self._initialized,
            'buffer_size': len(self.buffer),
            'required_size': self.required_lookback,
            'ready': self.is_ready(),
            'coverage_pct': (len(self.buffer) / self.required_lookback) * 100 if self.required_lookback > 0 else 0
        }
