"""
Live Candles Repository - WebSocket/SQLite ONLY
================================================

CRITICAL: This module must NEVER import:
- IntradayStore
- pd.read_parquet
- Any references to artifacts/data_m*

Architecture tests enforce this constraint.
"""

from typing import Optional
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)


class LiveCandlesRepository:
    """
    Load live candle data from WebSocket SQLite database.

    Data Source: SQLite only (WebSocket feed)
    Retention: 30 days (configurable via ENV)
    Universe: Up to 50 symbols (WebSocket limit)
    Sessions: All sessions included (pre/after market)

    Architecture: Part of Live data pipeline - NEVER touches Parquet.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize repository.

        Args:
            db_path: Optional override for DB path (mainly for testing)
        """
        # SSOT: Use ENV for DB path with sensible defaults
        if db_path is None:
            db_path = os.getenv(
                'LIVE_MARKETDATA_DB',
                '/opt/trading/marketdata-stream/data/market_data.db'
            )

        self.db_path = Path(db_path)
        self.retention_days = int(os.getenv('LIVE_RETENTION_DAYS', '30'))

        logger.info(f"📊 LiveCandlesRepository initialized")
        logger.info(f"   DB: {self.db_path}")
        logger.info(f"   Retention: {self.retention_days} days")
        logger.info(f"   Source: LIVE_SQLITE")

    def load_candles(
        self,
        symbol: str,
        timeframe: str,  # M1, M5, M15
        limit: int = 500,
        date_filter: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Load live candles from SQLite.

        Args:
            symbol: Stock symbol
            timeframe: M1, M5, or M15
            limit: Max number of candles to return
            date_filter: Optional date filter (for historical view)

        Returns:
            DataFrame with:
            - index: timestamp (tz-aware, America/New_York)
            - columns: open, high, low, close, volume
        """
        if not self.db_path.exists():
            logger.warning(f"⚠️  Live DB not found: {self.db_path}")
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

        try:
            conn = sqlite3.connect(str(self.db_path))

            # Build query
            # SQLite stores timestamp as milliseconds
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM candles
                WHERE symbol = ? AND interval = ?
            """
            params = [symbol, timeframe]

            # Optional date filter
            if date_filter is not None:
                query += " AND DATE(timestamp/1000, 'unixepoch') = ?"
                params.append(date_filter.isoformat())

            query += " ORDER BY timestamp ASC LIMIT ?"
            params.append(limit)

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            if df.empty:
                logger.debug(f"No live data for {symbol} {timeframe}")
                return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

            # Convert timestamp from milliseconds to datetime (tz-aware)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)

            # Convert to America/New_York timezone (market hours)
            df['timestamp'] = df['timestamp'].dt.tz_convert('America/New_York')

            # Set as index
            df = df.set_index('timestamp')

            logger.debug(f"✅ Loaded {len(df)} live candles: {symbol} {timeframe}")

            return df

        except Exception as e:
            logger.error(f"Error loading live candles: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

    def get_freshness(self, symbol: str, timeframe: str) -> dict:
        """
        Get data freshness for telemetry.

        Args:
            symbol: Stock symbol
            timeframe: M1, M5, M15

        Returns:
            {
                'last_timestamp': pd.Timestamp or None,
                'age_minutes': float or None,
                'row_count': int,
                'source': 'LIVE_SQLITE'
            }
        """
        if not self.db_path.exists():
            return {
                'last_timestamp': None,
                'age_minutes': None,
                'row_count': 0,
                'source': 'LIVE_SQLITE'
            }

        try:
            conn = sqlite3.connect(str(self.db_path))

            # Get row count
            count_query = """
                SELECT COUNT(*) as count
                FROM candles
                WHERE symbol = ? AND interval = ?
            """
            cursor = conn.execute(count_query, (symbol, timeframe))
            row_count = cursor.fetchone()[0]

            # Get latest timestamp
            latest_query = """
                SELECT MAX(timestamp) as last_ts
                FROM candles
                WHERE symbol = ? AND interval = ?
            """
            cursor = conn.execute(latest_query, (symbol, timeframe))
            last_ts_ms = cursor.fetchone()[0]

            conn.close()

            if last_ts_ms is None:
                return {
                    'last_timestamp': None,
                    'age_minutes': None,
                    'row_count': row_count,
                    'source': 'LIVE_SQLITE'
                }

            # Convert to timestamp
            last_timestamp = pd.Timestamp(last_ts_ms, unit='ms', tz='America/New_York')

            # Calculate age
            now = pd.Timestamp.now(tz='America/New_York')
            age = now - last_timestamp
            age_minutes = age.total_seconds() / 60

            return {
                'last_timestamp': last_timestamp,
                'age_minutes': age_minutes,
                'row_count': row_count,
                'source': 'LIVE_SQLITE'
            }

        except Exception as e:
            logger.error(f"Error getting freshness: {e}")
            return {
                'last_timestamp': None,
                'age_minutes': None,
                'row_count': 0,
                'source': 'LIVE_SQLITE'
            }

    def get_available_symbols(self) -> list[str]:
        """
        Get list of symbols with live data.

        Returns:
            List of symbol strings
        """
        if not self.db_path.exists():
            return []

        try:
            conn = sqlite3.connect(str(self.db_path))
            query = "SELECT DISTINCT symbol FROM candles ORDER BY symbol"
            cursor = conn.execute(query)
            symbols = [row[0] for row in cursor.fetchall()]
            conn.close()
            return symbols
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return []
