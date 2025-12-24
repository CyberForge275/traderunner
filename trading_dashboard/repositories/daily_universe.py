"""
Daily Universe Repository - Parquet-only adapter for universe data.

CRITICAL ARCHITECTURE RULES:
- Data source: universe/stocks_data.parquet ONLY
- No sqlite3, no live data sources
- LRU cache for performance (61MB universe file)
- Timezone: America/New_York
- Output: lowercase columns (open, high, low, close, volume)
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional
import pandas as pd
import logging

from axiom_bt.daily import DailyStore

logger = logging.getLogger(__name__)


class DailyUniverseRepository:
    """
    Parquet-only repository for daily OHLCV from universe.

    Data Source: data/universe/stocks_data.parquet
    Coverage: 6,534 US stocks, 2023-03-01 to 2025-12-03
    Normalization: TZ-aware (America/New_York), lowercase OHLCV
    Performance: LRU cache on universe load, slice per symbol

    Architecture: Part of Backtesting data pipeline - NEVER touches SQLite.
    """

    def __init__(self, universe_path: Optional[Path] = None):
        """
        Initialize repository.

        Args:
            universe_path: Path to universe parquet. Defaults to data/universe/stocks_data.parquet
        """
        if universe_path is None:
            # Default to project structure
            universe_path = Path('data/universe/stocks_data.parquet')

        self.universe_path = universe_path
        self.daily_store = DailyStore()

        if not self.universe_path.exists():
            logger.warning(f"⚠️  Universe parquet not found: {self.universe_path}")
        else:
            logger.info(f"📊 DailyUniverseRepository initialized")
            logger.info(f"   Source: {self.universe_path}")
            logger.info(f"   Data: UNIVERSE_PARQUET")

    @lru_cache(maxsize=1)
    def _load_universe(self, tz: str) -> pd.DataFrame:
        """
        Cache universe load (61MB parquet).

        Returns normalized DataFrame with columns:
        ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        if not self.universe_path.exists():
            raise FileNotFoundError(f"Universe parquet not found: {self.universe_path}")

        logger.info(f"Loading universe parquet from {self.universe_path}")
        df = self.daily_store.load_universe(
            universe_path=self.universe_path,
            tz=tz
        )
        logger.info(f"Loaded {len(df)} rows, {df['symbol'].nunique()} symbols")
        return df

    def load_symbol(
        self,
        symbol: str,
        tz: str = "America/New_York"
    ) -> pd.DataFrame:
        """
        Load D1 data for single symbol.

        Args:
            symbol: Stock symbol (case-insensitive)
            tz: Output timezone (default: America/New_York)

        Returns:
            DataFrame with:
            - index: timestamp (tz-aware)
            - columns: open, high, low, close, volume
        """
        symbol = symbol.strip().upper()

        # Load cached universe
        df_all = self._load_universe(tz)

        # Filter for symbol
        df = df_all[df_all['symbol'] == symbol].copy()

        if df.empty:
            logger.warning(f"Symbol {symbol} not found in universe")
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

        # Set timestamp as index
        df = df.set_index('timestamp')

        # Return OHLCV columns only
        result = df[['open', 'high', 'low', 'close', 'volume']].copy()

        logger.debug(
            f"Loaded {len(result)} days for {symbol} "
            f"({result.index.min().date()} to {result.index.max().date()})"
        )

        return result

    def has_symbol(self, symbol: str, tz: str = "America/New_York") -> bool:
        """
        Check if symbol exists in universe.

        Args:
            symbol: Stock symbol
            tz: Timezone for loading

        Returns:
            True if symbol has data
        """
        try:
            df_all = self._load_universe(tz)
            return symbol.strip().upper() in df_all['symbol'].values
        except FileNotFoundError:
            return False

    def get_symbols(self, tz: str = "America/New_York") -> list[str]:
        """
        Get list of all available symbols in universe.

        Returns:
            Sorted list of symbol strings
        """
        try:
            df_all = self._load_universe(tz)
            return sorted(df_all['symbol'].unique().tolist())
        except FileNotFoundError:
            return []

    def get_date_range(
        self,
        symbol: str,
        tz: str = "America/New_York"
    ) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
        """
        Get date range for a symbol.

        Args:
            symbol: Stock symbol
            tz: Timezone

        Returns:
            (first_date, last_date) or (None, None) if not found
        """
        df = self.load_symbol(symbol, tz)
        if df.empty:
            return (None, None)

        return (df.index.min(), df.index.max())
