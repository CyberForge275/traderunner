"""
Historical Provider Interface

Protocol for fetching missing historical data during backfill.
"""

from typing import Protocol
import pandas as pd


class HistoricalProvider(Protocol):
    """
    Protocol for fetching historical data.

    Implementations can use:
    - EODHD API
    - Backtest parquet (read-only)
    - Other providers

    CRITICAL: Providers must respect data segregation.
    They can READ backtest parquet but never WRITE.
    """

    def fetch_bars(
        self,
        symbol: str,
        tf: str,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp
    ) -> pd.DataFrame:
        """
        Fetch bars for given range.

        Args:
            symbol: Stock symbol
            tf: Timeframe (M1/M5/M15)
            start_ts: Start timestamp (timezone-aware)
            end_ts: End timestamp (timezone-aware)

        Returns:
            DataFrame with OHLCV data (timezone-aware DatetimeIndex)
            Empty DataFrame if no data available

        Raises:
            Exception on fetch failures (network, auth, etc.)
        """
        ...
