"""
InsideBar Strategy Data Loader

Integrates DatabaseLoader and BufferManager for InsideBar strategy use.
Ensures consistent data loading with RTH filtering and automatic backfill.
"""
import asyncio
from typing import Optional
import pandas as pd
import logging
from pathlib import Path

from trading_dashboard.data_loading.loaders.database_loader import DatabaseLoader
from trading_dashboard.data_loading.buffer_manager import BufferManager


logger = logging.getLogger(__name__)


class InsideBarDataLoader:
    """
    Data loader specifically for InsideBar strategy.
    
    Features:
    - Loads from database (single source of truth)
    - Auto-backfill from EODHD if needed
    - RTH-only filtering (9:30-16:00 ET)
    - Maintains 50-candle rolling buffer for ATR calculation
    - Ensures session continuity
    
    Usage:
        loader = InsideBarDataLoader(symbol='APP', interval='M5')
        await loader.initialize()
        
        # Get buffer for strategy
        candles = loader.get_candles()
        
        # Add new candle (live trading)
        loader.add_candle({...})
    """
    
    def __init__(
        self,
        symbol: str,
        interval: str = 'M5',
        lookback_candles: int = 50,
        db_path: Optional[str] = None,
        backfill_enabled: bool = True,
        api_key: Optional[str] = None
    ):
        """
        Initialize InsideBar data loader.
        
        Args:
            symbol: Trading symbol (e.g., 'APP')
            interval: Candle interval (default: 'M5')
            lookback_candles: Number of candles to maintain (default: 50)
            db_path: Path to database (auto-detect if None)
            backfill_enabled: Enable EODHD backfill (default: True)
            api_key: EODHD API key (optional, reads from env)
        """
        self.symbol = symbol
        self.interval = interval
        self.lookback_candles = lookback_candles
        
        # Initialize database loader
        self.db_loader = DatabaseLoader(
            db_path=db_path,
            backfill_enabled=backfill_enabled,
            api_key=api_key
        )
        
        # Initialize buffer manager
        self.buffer_mgr = BufferManager(required_lookback=lookback_candles)
        
        self._initialized = False
        
        logger.info(
            f"InsideBarDataLoader created: {symbol} {interval}, "
            f"lookback={lookback_candles}"
        )
    
    async def initialize(self, force_reload: bool = False):
        """
        Initialize data loader by loading historical candles.
        
        This should be called once before using the loader.
        
        Args:
            force_reload: Force reload even if already initialized
            
        Raises:
            ValueError: If initialization fails
        """
        if self._initialized and not force_reload:
            logger.info("Already initialized, skipping")
            return
        
        logger.info(
            f"Initializing InsideBarDataLoader for {self.symbol} {self.interval}..."
        )
        
        # Load required candles from database (with auto-backfill)
        candles = await self.db_loader.load_candles(
            symbol=self.symbol,
            interval=self.interval,
            required_count=self.lookback_candles,
            session='RTH'  # RTH-only for InsideBar
        )
        
        if len(candles) < self.lookback_candles:
            logger.warning(
                f"Only {len(candles)}/{self.lookback_candles} candles available"
            )
        
        # Initialize buffer
        self.buffer_mgr.initialize(candles)
        
        self._initialized = True
        
        status = self.buffer_mgr.get_readiness_status()
        logger.info(
            f"✅ Initialized: {status['buffer_size']} candles, "
            f"{status['coverage_pct']:.1f}% coverage"
        )
    
    def add_candle(self, candle: dict):
        """
        Add new candle to buffer (for live trading).
        
        Args:
            candle: Dictionary with candle data
                    Required keys: timestamp, open, high, low, close, volume
        """
        if not self._initialized:
            raise RuntimeError("Loader not initialized. Call initialize() first.")
        
        self.buffer_mgr.add_candle(candle)
        
        logger.debug(
            f"Added candle: {candle.get('timestamp')} "
            f"close={candle.get('close')}"
        )
    
    def get_candles(self) -> pd.DataFrame:
        """
        Get current buffer as DataFrame for strategy processing.
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
            Sorted by timestamp (oldest first)
            
        Raises:
            RuntimeError: If loader not initialized
        """
        if not self._initialized:
            raise RuntimeError("Loader not initialized. Call initialize() first.")
        
        return self.buffer_mgr.get_buffer()
    
    def is_ready(self) -> bool:
        """Check if loader has sufficient data for strategy."""
        return self._initialized and self.buffer_mgr.is_ready()
    
    def get_status(self) -> dict:
        """
        Get detailed status of data loader.
        
        Returns:
            Dictionary with initialization status, buffer status, and readiness
        """
        base_status = {
            'symbol': self.symbol,
            'interval': self.interval,
            'lookback_required': self.lookback_candles,
            'initialized': self._initialized,
            'database_path': self.db_loader.db_path if self._initialized else None
        }
        
        if self._initialized:
            buffer_status = self.buffer_mgr.get_readiness_status()
            base_status.update(buffer_status)
        
        return base_status


# Convenience function for quick initialization
async def create_insidebar_loader(
    symbol: str,
    interval: str = 'M5',
    lookback: int = 50
) -> InsideBarDataLoader:
    """
    Create and initialize InsideBar data loader (convenience function).
    
    Args:
        symbol: Trading symbol
        interval: Candle interval (default: 'M5')
        lookback: Number of candles to maintain (default: 50)
        
    Returns:
        Initialized InsideBarDataLoader instance
        
    Example:
        loader = await create_insidebar_loader('APP')
        candles = loader.get_candles()
    """
    loader = InsideBarDataLoader(
        symbol=symbol,
        interval=interval,
        lookback_candles=lookback
    )
    
    await loader.initialize()
    
    return loader
