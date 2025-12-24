"""
SQLite Cache for Pre-Paper Runtime History

Writable cache for hybrid data (historical + websocket).

CRITICAL INVARIANTS:
- No duplicates (PRIMARY KEY enforced)
- Monotonic retrieval (ORDER BY ts)
- TZ normalization (store UTC, document market_tz)
- Source tracking (historical vs websocket)
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List
import pandas as pd

logger = logging.getLogger(__name__)


class SQLiteCache:
    """
    SQLite cache for Pre-Paper runtime history.
    
    Schema:
        bars(symbol, tf, ts, market_tz, open, high, low, close, volume, source, inserted_at)
    
    Operations:
        - append_bar(): Add single bar (WebSocket stream)
        - append_bars(): Batch insert (backfill)
        - get_bars(): Retrieve range
        - get_range(): Get cached min/max
    """
    
    def __init__(self, db_path: Path):
        """
        Args:
            db_path: Path to pre_paper_cache.db
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_schema()
    
    def _init_schema(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bars (
                symbol TEXT NOT NULL,
                tf TEXT NOT NULL,
                ts INTEGER NOT NULL,  -- Unix timestamp (UTC)
                market_tz TEXT NOT NULL,  -- Always 'America/New_York'
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                source TEXT,  -- 'historical' | 'websocket' | 'backfill'
                inserted_at INTEGER NOT NULL,  -- Unix timestamp
                PRIMARY KEY (symbol, tf, ts)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bars_range 
            ON bars(symbol, tf, ts)
        """)
        
        self.conn.commit()
        logger.info(f"Initialized SQLite cache: {self.db_path}")
    
    def append_bar(
        self,
        symbol: str,
        tf: str,
        ts: pd.Timestamp,
        ohlcv: dict,
        source: str = "websocket"
    ):
        """
        Append single bar (e.g., from WebSocket stream).
        
        Args:
            symbol: Stock symbol
            tf: Timeframe (M1/M5/M15)
            ts: Timestamp (timezone-aware)
            ohlcv: Dict with open, high, low, close, volume
            source: Data source ('websocket', 'historical', 'backfill')
        """
        cursor = self.conn.cursor()
        
        # Convert to UTC timestamp
        ts_utc = int(ts.tz_convert('UTC').timestamp())
        inserted_at = int(pd.Timestamp.now(tz='UTC').timestamp())
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO bars 
                (symbol, tf, ts, market_tz, open, high, low, close, volume, source, inserted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                tf,
                ts_utc,
                "America/New_York",  # IMMUTABLE
                ohlcv["open"],
                ohlcv["high"],
                ohlcv["low"],
                ohlcv["close"],
                ohlcv["volume"],
                source,
                inserted_at
            ))
            
            self.conn.commit()
            logger.debug(f"Appended bar: {symbol} {tf} {ts} ({source})")
        
        except sqlite3.IntegrityError as e:
            # Duplicate - expected for idempotent appends
            logger.debug(f"Bar already exists: {symbol} {tf} {ts}")
    
    def append_bars(
        self,
        symbol: str,
        tf: str,
        df: pd.DataFrame,
        source: str = "backfill"
    ):
        """
        Batch append bars (e.g., from backfill).
        
        Args:
            symbol: Stock symbol
            tf: Timeframe
            df: DataFrame with OHLCV (timezone-aware DatetimeIndex)
            source: Data source
        """
        cursor = self.conn.cursor()
        inserted_at = int(pd.Timestamp.now(tz='UTC').timestamp())
        
        # Convert to UTC timestamps
        df = df.copy()
        df.index = df.index.tz_convert('UTC')
        
        rows = [
            (
                symbol,
                tf,
                int(ts.timestamp()),
                "America/New_York",
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                source,
                inserted_at
            )
            for ts, row in df.iterrows()
        ]
        
        cursor.executemany("""
            INSERT OR REPLACE INTO bars 
            (symbol, tf, ts, market_tz, open, high, low, close, volume, source, inserted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        
        self.conn.commit()
        logger.info(f"Appended {len(rows)} bars: {symbol} {tf} ({source})")
    
    def get_bars(
        self,
        symbol: str,
        tf: str,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None
    ) -> pd.DataFrame:
        """
        Retrieve bars for given range.
        
        Args:
            symbol: Stock symbol
            tf: Timeframe
            start_ts: Start timestamp (inclusive, optional)
            end_ts: End timestamp (inclusive, optional)
        
        Returns:
            DataFrame with OHLCV (timezone-aware index in America/New_York)
        """
        cursor = self.conn.cursor()
        
        # Build query
        query = """
            SELECT ts, open, high, low, close, volume
            FROM bars
            WHERE symbol = ? AND tf = ?
        """
        params = [symbol, tf]
        
        if start_ts:
            query += " AND ts >= ?"
            params.append(int(start_ts.tz_convert('UTC').timestamp()))
        
        if end_ts:
            query += " AND ts <= ?"
            params.append(int(end_ts.tz_convert('UTC').timestamp()))
        
        query += " ORDER BY ts"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            # Return empty DataFrame with correct columns
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        
        # Convert to DataFrame
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        
        # Convert timestamps to DatetimeIndex (market_tz)
        df["ts"] = pd.to_datetime(df["ts"], unit="s", utc=True)
        df["ts"] = df["ts"].dt.tz_convert("America/New_York")
        df.set_index("ts", inplace=True)
        
        return df
    
    def get_range(self, symbol: str, tf: str) -> Optional[tuple]:
        """
        Get cached range (min, max) timestamps.
        
        Args:
            symbol: Stock symbol
            tf: Timeframe
        
        Returns:
            Tuple of (min_ts, max_ts) or None if no data
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT MIN(ts), MAX(ts)
            FROM bars
            WHERE symbol = ? AND tf = ?
        """, (symbol, tf))
        
        row = cursor.fetchone()
        
        if row and row[0] is not None:
            min_ts = pd.Timestamp(row[0], unit="s", tz="UTC").tz_convert("America/New_York")
            max_ts = pd.Timestamp(row[1], unit="s", tz="UTC").tz_convert("America/New_York")
            return (min_ts, max_ts)
        
        return None
    
    def close(self):
        """Close database connection."""
        self.conn.close()
        logger.info(f"Closed SQLite cache: {self.db_path}")
