"""
Backtesting Timeframe Resolver - Routes timeframes to correct data sources.

CRITICAL ARCHITECTURE RULES:
- M1/M5/M15 → IntradayStore (parquet: artifacts/data_m*/)
- D1 → DailyUniverseRepository (parquet: data/universe/stocks_data.parquet)
- H1 → Resample from M5 (if available)
- NO sqlite3, NO live data sources
"""

from pathlib import Path
from typing import Optional
import pandas as pd
import logging

from trading_dashboard.repositories.daily_universe import DailyUniverseRepository
from trading_dashboard.providers.ohlcv_contract import OhlcvRequest, OhlcvProvider
from trading_dashboard.providers.axiom_bt_provider import AxiomBtProvider

logger = logging.getLogger(__name__)


class BacktestingTimeframeResolver:
    """
    Resolve timeframe requests to appropriate Parquet-only data source.

    Routing:
    - M1/M5/M15 → OhlcvProvider (default: AxiomBtProvider → IntradayStore)
    - D1 → DailyUniverseRepository (universe parquet)
    - H1 → Resample from M5 or M1 (if available)

    All data sources are Parquet-only (no SQLite, no live data).
    """

    def __init__(self, universe_path: Optional[Path] = None, ohlcv_provider: Optional[OhlcvProvider] = None):
        """
        Initialize resolver with data sources.

        Args:
            universe_path: Optional custom path to universe parquet
            ohlcv_provider: Optional OHLCV provider (default: AxiomBtProvider)
        """
        # Use injected provider or default to AxiomBtProvider
        self.ohlcv_provider = ohlcv_provider or AxiomBtProvider()
        self.daily_repo = DailyUniverseRepository(universe_path=universe_path)

        logger.info("📍 BacktestingTimeframeResolver initialized")
        logger.info(f"   Intraday: {self.ohlcv_provider.__class__.__name__}")
        logger.info("   Daily: DailyUniverseRepository (universe parquet)")
        logger.info("   H1: Resample from M5")

    def load(
        self,
        symbol: str,
        timeframe: str,
        tz: str = "America/New_York"
    ) -> pd.DataFrame:
        """
        Load data for symbol/timeframe from correct source.

        Args:
            symbol: Stock symbol
            timeframe: M1, M5, M15, H1, or D1
            tz: Output timezone

        Returns:
            DataFrame with:
            - index: timestamp (tz-aware)
            - columns: open, high, low, close, volume

        Raises:
            ValueError: If timeframe is unsupported
            FileNotFoundError: If data file doesn't exist
        """
        symbol = symbol.strip().upper()
        timeframe = timeframe.upper()

        logger.debug(f"Resolving {symbol} {timeframe} via {self._get_source(timeframe)}")

        if timeframe in ['M1', 'M5', 'M15']:
            return self._load_intraday(symbol, timeframe, tz)

        elif timeframe == 'D1':
            return self._load_daily(symbol, tz)

        elif timeframe == 'H1':
            return self._load_h1(symbol, tz)

        else:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}. "
                f"Supported: M1, M5, M15, H1, D1"
            )

    def _load_intraday(
        self,
        symbol: str,
        timeframe: str,
        tz: str
    ) -> pd.DataFrame:
        """Load intraday data from OhlcvProvider.
        
        Creates a Full-Load request (no start/end, warmup_bars=None).
        """
        req = OhlcvRequest(
            symbol=symbol,
            timeframe=timeframe,
            tz=tz,
            start=None,  # Full-Load
            end=None,
            warmup_bars=None,  # MUST be None for Full-Load
            session_mode=None  # Use provider default (axiom_bt: "rth")
        )
        
        df, meta = self.ohlcv_provider.get_ohlcv(req)
        logger.debug(f"Loaded {meta.row_count_total} rows via {meta.provider_id}")
        return df

    def _load_daily(self, symbol: str, tz: str) -> pd.DataFrame:
        """Load daily data from DailyUniverseRepository."""
        return self.daily_repo.load_symbol(symbol, tz=tz)

    def _load_h1(self, symbol: str, tz: str) -> pd.DataFrame:
        """
        Load H1 by resampling from M5 (or M1 if M5 unavailable).

        Strategy:
        1. Try loading M5 via provider
        2. Resample to 1H
        3. If M5 missing, try M1 (fallback)
        """
        try:
            # Try M5 first (faster)
            req = OhlcvRequest(
                symbol=symbol,
                timeframe="M5",
                tz=tz,
                start=None,
                end=None,
                warmup_bars=None,
                session_mode=None
            )
            df_m5, _ = self.ohlcv_provider.get_ohlcv(req)

            if df_m5.empty:
                raise FileNotFoundError(f"M5 data empty for {symbol}")

            # Resample to 1H
            df_h1 = df_m5.resample('1H').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

            logger.debug(f"Resampled H1 from M5: {len(df_h1)} bars for {symbol}")
            return df_h1

        except FileNotFoundError as e:
            # M5 not available, try M1 fallback
            logger.debug(f"M5 not available for {symbol}, trying M1 fallback")

            try:
                req = OhlcvRequest(
                    symbol=symbol,
                    timeframe="M1",
                    tz=tz,
                    start=None,
                    end=None,
                    warmup_bars=None,
                    session_mode=None
                )
                df_m1, _ = self.ohlcv_provider.get_ohlcv(req)

                if df_m1.empty:
                    raise FileNotFoundError(f"M1 data empty for {symbol}")

                # Resample to 1H
                df_h1 = df_m1.resample('1H').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()

                logger.debug(f"Resampled H1 from M1: {len(df_h1)} bars for {symbol}")
                return df_h1

            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Cannot derive H1 for {symbol}: neither M5 nor M1 available"
                )

    def has_data(self, symbol: str, timeframe: str) -> bool:
        """
        Check if data is available for symbol/timeframe.

        Args:
            symbol: Stock symbol
            timeframe: M1, M5, M15, H1, or D1

        Returns:
            True if data exists or can be derived
        """
        timeframe = timeframe.upper()

        try:
            if timeframe in ['M1', 'M5', 'M15']:
                # Try loading via provider
                req = OhlcvRequest(
                    symbol=symbol,
                    timeframe=timeframe,
                    tz=None,
                    start=None,
                    end=None,
                    warmup_bars=None,
                    session_mode=None
                )
                df, _ = self.ohlcv_provider.get_ohlcv(req)
                return len(df) > 0

            elif timeframe == 'D1':
                return self.daily_repo.has_symbol(symbol)

            elif timeframe == 'H1':
                # H1 available if M5 OR M1 exists
                has_m5 = self.has_data(symbol, 'M5')
                has_m1 = self.has_data(symbol, 'M1')
                return has_m5 or has_m1

            else:
                return False

        except Exception as e:
            logger.debug(f"Error checking {symbol} {timeframe}: {e}")
            return False

    def _get_source(self, timeframe: str) -> str:
        """Get human-readable source name for timeframe."""
        if timeframe in ['M1', 'M5', 'M15']:
            return f"{self.ohlcv_provider.__class__.__name__}"
        elif timeframe == 'D1':
            return "DailyUniverseRepository"
        elif timeframe == 'H1':
            return "Resample(M5)"
        else:
            return "Unknown"
