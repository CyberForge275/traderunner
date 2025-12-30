"""EODHD historical data backfill with RTH filtering."""
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import logging
import aiohttp

from ..filters.session_filter import SessionFilter


logger = logging.getLogger(__name__)


class EODHDBackfill:
    """Backfill missing candles from EODHD API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize EODHD backfill.

        Args:
            api_key: EODHD API key (optional, reads from env if None)
        """
        if api_key is None:
            import os
            api_key = os.getenv('EODHD_API_KEY')

        if not api_key:
            raise ValueError("EODHD_API_KEY not provided and not found in environment")

        self.api_key = api_key
        self.session_filter = SessionFilter()
        self.base_url = "https://eodhd.com/api/intraday"

    async def fetch_rth_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = '5m'
    ) -> pd.DataFrame:
        """
        Fetch RTH-only candles from EODHD.

        Args:
            symbol: Trading symbol (e.g., 'APP')
            start: Start datetime (UTC or timezone-aware)
            end: End datetime (UTC or timezone-aware)
            interval: Candle interval (default: '5m')

        Returns:
            DataFrame with RTH candles only
            Columns: timestamp, open, high, low, close, volume

        Raises:
            ValueError: If date range invalid
            aiohttp.ClientError: If EODHD API fails
        """
        if start >= end:
            raise ValueError(f"Start {start} must be before end {end}")

        logger.info(
            f"EODHD backfill: {symbol} from {start} to {end} ({interval})"
        )

        # Fetch from EODHD (includes all sessions)
        raw_data = await self._fetch_from_api(
            symbol=symbol,
            interval=interval,
            start=start,
            end=end
        )

        if raw_data.empty:
            logger.warning(f"EODHD returned no data for {symbol}")
            return raw_data

        logger.info(f"EODHD raw: {len(raw_data)} candles (all sessions)")

        # Filter to RTH only
        rth_data = self.session_filter.filter_to_rth(raw_data)

        logger.info(
            f"EODHD filtered: {len(rth_data)} RTH candles "
            f"({len(raw_data) - len(rth_data)} removed)"
        )

        return rth_data

    async def _fetch_from_api(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """
        Fetch raw data from EODHD API.

        Args:
            symbol: Trading symbol
            interval: Interval (5m, 1m, etc.)
            start: Start datetime
            end: End datetime

        Returns:
            Raw DataFrame from EODHD
        """
        # Format dates for API (YYYY-MM-DD HH:MM:SS in UTC)
        from_ts = int(start.timestamp())
        to_ts = int(end.timestamp())

        # Build URL
        url = (
            f"{self.base_url}/{symbol}.US"
            f"?api_token={self.api_key}"
            f"&interval={interval}"
            f"&from={from_ts}"
            f"&to={to_ts}"
            f"&fmt=json"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise aiohttp.ClientError(
                        f"EODHD API error {response.status}: {error_text}"
                    )

                data = await response.json()

                # Convert to DataFrame
                if not data:
                    return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

                df = pd.DataFrame(data)

                # Normalize column names
                # EODHD returns: timestamp, open, high, low, close, volume
                if 'datetime' in df.columns:
                    df = df.rename(columns={'datetime': 'timestamp'})

                # Convert timestamp to datetime
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

                # Ensure required columns
                required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                for col in required_cols:
                    if col not in df.columns:
                        logger.warning(f"Column '{col}' missing from EODHD response")

                return df[required_cols]

    def estimate_candle_count(
        self,
        start: datetime,
        end: datetime,
        interval_minutes: int = 5
    ) -> int:
        """
        Estimate expected number of RTH candles in date range.

        Useful for validating backfill completeness.

        Args:
            start: Start datetime
            end: End datetime
            interval_minutes: Candle interval in minutes (default: 5)

        Returns:
            Estimated candle count
        """
        # RTH: 9:30-16:00 = 6.5 hours = 390 minutes
        rth_minutes = 390
        candles_per_day = rth_minutes // interval_minutes  # 78 for M5

        # Count business days
        business_days = pd.bdate_range(start, end).size

        return candles_per_day * business_days
