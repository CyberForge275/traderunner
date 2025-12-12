"""Database loader for strategy candles with automatic backfill."""
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import logging
import sqlite3
from pathlib import Path

from ..filters.session_filter import SessionFilter
from .eodhd_backfill import EODHDBackfill


logger = logging.getLogger(__name__)


class DatabaseLoader:
    """
    Load candle data from database with automatic EODHD backfill.
    
    Single source of truth: All reads from database only.
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        backfill_enabled: bool = True,
        api_key: Optional[str] = None
    ):
        """
        Initialize database loader.
        
        Args:
            db_path: Path to SQLite database (auto-detect if None)
            backfill_enabled: Auto-backfill missing data (default: True)
            api_key: EODHD API key (optional)
        """
        # Auto-detect database path if not provided
        if db_path is None:
            db_paths = [
                Path("/opt/trading/marketdata-stream/data/market_data.db"),
                Path.home() / "data/workspace/droid/marketdata-stream/data/market_data.db"
            ]
            for path in db_paths:
                if path.exists():
                    db_path = str(path)
                    logger.info(f"Auto-detected database: {db_path}")
                    break
            
            if db_path is None:
                raise FileNotFoundError("Market data database not found")
        
        self.db_path = db_path
        self.backfill_enabled = backfill_enabled
        self.backfiller = EODHDBackfill(api_key) if backfill_enabled else None
        self.session_filter = SessionFilter()
    
    async def load_candles(
        self,
        symbol: str,
        interval: str,
        required_count: int,
        session: str = 'RTH'
    ) -> pd.DataFrame:
        """
        Load required number of most recent candles.
        
        Workflow:
        1. Query database for required_count candles
        2. If insufficient → Trigger backfill from EODHD
        3. Insert into database
        4. Re-query database
        5. Return candles
        
        Args:
            symbol: Trading symbol
            interval: Candle interval (e.g., 'M5')
            required_count: Number of candles needed
            session: Session filter ('RTH' | 'ALL')
            
        Returns:
            DataFrame with requested candles, sorted by timestamp (oldest first)
            
        Raises:
            ValueError: If backfill fails and count still insufficient
        """
        logger.info(
            f"Loading {required_count} {interval} candles for {symbol} ({session})"
        )
        
        # Step 1: Query database
        db_candles = self._get_recent_candles(
            symbol=symbol,
            interval=interval,
            limit=required_count,
            session=session
        )
        
        if len(db_candles) >= required_count:
            logger.info(f"✅ DB has {len(db_candles)} candles (sufficient)")
            return db_candles.sort_values('timestamp').reset_index(drop=True)
        
        # Step 2: Insufficient data → Backfill
        logger.warning(
            f"⚠️  DB has only {len(db_candles)}/{required_count} candles"
        )
        
        if not self.backfill_enabled:
            raise ValueError(
                f"Insufficient data ({len(db_candles)}/{required_count}) "
                f"and backfill disabled"
            )
        
        # Calculate backfill range
        await self._backfill_missing_data(
            symbol=symbol,
            interval=interval,
            required_count=required_count,
            session=session
        )
        
        # Step 3: Re-query after backfill
        db_candles_after = self._get_recent_candles(
            symbol=symbol,
            interval=interval,
            limit=required_count,
            session=session
        )
        
        if len(db_candles_after) < required_count:
            raise ValueError(
                f"Backfill completed but still insufficient data: "
                f"{len(db_candles_after)}/{required_count}"
            )
        
        logger.info(f"✅ After backfill: {len(db_candles_after)} candles")
        return db_candles_after.sort_values('timestamp').reset_index(drop=True)
    
    def _get_recent_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
        session: str = 'RTH'
    ) -> pd.DataFrame:
        """
        Query database for recent candles.
        
        Args:
            symbol: Trading symbol
            interval: Interval (M5, M1, etc.)
            limit: Max candles to return
            session: Session filter
            
        Returns:
            DataFrame with candles
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            
            # Query for recent candles
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM candles
                WHERE symbol = ?
                AND interval = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            
            df = pd.read_sql_query(
                query,
                conn,
                params=(symbol, interval, limit)
            )
            
            conn.close()
            
            if df.empty:
                return df
            
            # Convert timestamp from milliseconds to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            
            # Apply session filter if RTH requested
            if session == 'RTH':
                df = self.session_filter.filter_to_rth(df)
            
            logger.info(f"Retrieved {len(df)} candles from database")
            return df
            
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    async def _backfill_missing_data(
        self,
        symbol: str,
        interval: str,
        required_count: int,
        session: str
    ):
        """Backfill missing data from EODHD."""
        # Calculate time range (conservative: 2x required)
        interval_minutes = self._parse_interval_minutes(interval)
        lookback_minutes = required_count * interval_minutes * 2
        
        end = datetime.now()
        start = end - timedelta(minutes=lookback_minutes)
        
        logger.info(f"Backfilling from {start} to {end}...")
        
        # Fetch from EODHD (RTH-filtered)
        eodhd_candles = await self.backfiller.fetch_rth_candles(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval
        )
        
        if eodhd_candles.empty:
            logger.error("EODHD returned no data!")
            return
        
        # Insert into database
        self._insert_candles(
            symbol=symbol,
            interval=interval,
            candles=eodhd_candles
        )
        
        logger.info(f"✅ Inserted {len(eodhd_candles)} candles into DB")
    
    def _insert_candles(
        self,
        symbol: str,
        interval: str,
        candles: pd.DataFrame
    ):
        """
        Insert candles into database.
        
        Args:
            symbol: Trading symbol
            interval: Interval
            candles: DataFrame with candles
        """
        if candles.empty:
            return
        
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cursor = conn.cursor()
            
            # Convert timestamps to milliseconds
            candles = candles.copy()
            candles['timestamp_ms'] = (
                pd.to_datetime(candles['timestamp'])
                .astype('int64') // 10**6
            )
            
            # Insert candles (ignore duplicates)
            for _, row in candles.iterrows():
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO candles 
                    (timestamp, symbol, interval, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row['timestamp_ms'],
                        symbol,
                        interval,
                        row['open'],
                        row['high'],
                        row['low'],
                        row['close'],
                        row['volume']
                    )
                )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Inserted {len(candles)} candles for {symbol} {interval}")
            
        except Exception as e:
            logger.error(f"Failed to insert candles: {e}")
    
    @staticmethod
    def _parse_interval_minutes(interval: str) -> int:
        """Parse interval string to minutes (e.g., 'M5' → 5)."""
        if interval.startswith('M'):
            return int(interval[1:])
        elif interval.startswith('H'):
            return int(interval[1:]) * 60
        else:
            raise ValueError(f"Unsupported interval: {interval}")
