"""
Candles Repository
==================

Centralized access to market data for charts and analysis.
Uses central TradingSettings for all database paths.
"""

import sqlite3
from pathlib import Path
from typing import Optional
import pandas as pd
import logging
from datetime import datetime, timedelta

from src.core.settings import get_settings
from ..config import MARKETDATA_DIR


def get_candle_data(symbol: str, timeframe: str = "M5", hours: int = 24, reference_date = None, days_back: int = None) -> pd.DataFrame:
    """
    Get candle data for charting.

    Args:
        symbol: Stock symbol
        timeframe: M1, M5, M15, H1, D1
        hours: Hours of history to fetch (for intraday)
        reference_date: Specific date to fetch data for (date object or None for current)
        days_back: Days to load for D1 timeframe (overrides hours for daily data)

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    import logging
    logger = logging.getLogger(__name__)

    # For now, return mock data - will be replaced with actual DB query
    # TODO: Connect to actual candle database when available

    try:
        # Try to find candles in marketdata-stream data directory
        candles_path = MARKETDATA_DIR / "data" / "candles.db"

        if candles_path.exists():
            conn = sqlite3.connect(str(candles_path))

            since = datetime.now() - timedelta(hours=hours)

            query = f"""
                SELECT
                    datetime(timestamp) as timestamp,
                    open, high, low, close, volume
                FROM candles_{timeframe.lower()}
                WHERE symbol = ? AND timestamp > ?
                ORDER BY timestamp ASC
            """

            df = pd.read_sql_query(query, conn, params=[symbol, since.isoformat()])
            conn.close()

            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
    except Exception as e:
        print(f"Error loading candles from DB: {e}")

    # Try to load from parquet files (real data)
    try:
        from pathlib import Path
        from ..config import TRADERUNNER_DIR

        # Map timeframe to data directory
        timeframe_dirs = {
            "M1": "data_m1",
            "M5": "data_m5",
            "M15": "data_m15",
            "H1": "data_m5",  # Use M5 data for H1 (will resample)
            "D1": "data_d1"   # Daily data
        }

        # CRITICAL FIX: Don't fallback to M5 if timeframe not supported!
        if timeframe not in timeframe_dirs:
            logger.warning(f"⚠️  Unsupported timeframe: {timeframe}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        data_dir = timeframe_dirs[timeframe]

        # Special handling for D1 (Daily data from yearly universe files)
        if timeframe == "D1":
            logger.info(f"=" * 80)
            logger.info(f"📅 DAILY DATA (D1) LOADING FOR {symbol}")
            logger.info(f"=" * 80)
            logger.info(f"   days_back: {days_back}")
            logger.info(f"   reference_date: {reference_date}")

            try:
                from ..data_loading.loaders.daily_data_loader import DailyDataLoader
                logger.info(f"   ✅ DailyDataLoader imported")

                loader = DailyDataLoader()
                logger.info(f"   ✅ Loader initialized: {loader.data_dir}")

                # Check if data directory exists and has files
                import os
                if loader.data_dir.exists():
                    files = os.listdir(loader.data_dir)
                    logger.info(f"   ✅ Directory exists with {len(files)} files: {files}")
                else:
                    logger.error(f"   ❌ Directory does not exist: {loader.data_dir}")
                    return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

                # Use configurable days_back (default 180 if not specified)
                days_to_load = days_back if days_back is not None else 180
                logger.info(f"   Loading {days_to_load} days of daily data...")

                df = loader.load_data(symbol, days_back=days_to_load)

                if not df.empty:
                    logger.info(f"   ✅ SUCCESS: Loaded {len(df)} daily candles for {symbol}")
                    logger.info(f"   Columns: {list(df.columns)}")
                    logger.info(f"   Index type: {type(df.index)}")
                    logger.info(f"   First row: {df.iloc[0].to_dict() if len(df) > 0 else 'N/A'}")
                    logger.info(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
                    logger.info(f"=" * 80)
                    return df
                else:
                    logger.warning(f"   ⚠️  DataFrame is EMPTY for {symbol}")
                    logger.warning(f"=" * 80)
                    return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            except Exception as e:
                logger.error(f"   ❌ EXCEPTION in daily data loading:")
                logger.error(f"   Error type: {type(e).__name__}")
                logger.error(f"   Error message: {str(e)}")
                import traceback
                logger.error(f"   Traceback:\n{traceback.format_exc()}")
                logger.error(f"=" * 80)
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # For intraday (M1/M5/M15/H1), use parquet files
        parquet_path = TRADERUNNER_DIR / "artifacts" / data_dir / f"{symbol}.parquet"

        if parquet_path.exists():
            # Load parquet file
            df = pd.read_parquet(parquet_path)

            # Handle timestamp: it's typically the index
            if df.index.name == 'timestamp' or isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()

            # Ensure we have a timestamp column
            if 'timestamp' not in df.columns:
                # Try to find timestamp-like column
                for col in df.columns:
                    if 'time' in col.lower() or 'date' in col.lower():
                        df = df.rename(columns={col: 'timestamp'})
                        break

            # Normalize column names to lowercase
            df.columns = [col.lower() if col != 'timestamp' else col for col in df.columns]

            # Convert timestamp to datetime if needed
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Filter by reference_date for past dates; reject future dates.
            if reference_date is not None:
                from datetime import date as date_type, datetime
                if isinstance(reference_date, date_type):
                    ref_date = reference_date
                else:
                    ref_date = datetime.fromisoformat(str(reference_date)).date()

                today = datetime.now().date()
                if ref_date < today:
                    # User wants historical data - filter to that date
                    df = df[df['timestamp'].dt.date == ref_date]
                    logger.info(f"📅 Filtered to historical date: {ref_date}")
                elif ref_date > today:
                    # Never show future data, even if parquet contains candles.
                    logger.warning(f"Requested future date {ref_date}, returning empty")
                    return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                # If ref_date == today, show all available data (no filtering)

            # If we have data, return it
            if not df.empty:
                # Ensure required columns exist
                required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                if all(col in df.columns for col in required_cols):
                    return df[required_cols]

    except Exception as e:
        print(f"Error loading candles from parquet: {e}")

    # Only generate mock data if symbol doesn't have a parquet file
    # If parquet file exists but no data for selected date, return empty DataFrame
    from pathlib import Path
    from ..config import TRADERUNNER_DIR
    from datetime import date as date_type, datetime

    # Map timeframe to data directory
    timeframe_dirs = {
        "M1": "data_m1",
        "M5": "data_m5",
        "M15": "data_m15",
        "H1": "data_m5",  # Use M5 data for H1 (will resample)
        "D1": "data_d1"   # Daily data
    }

    # CRITICAL FIX: Don't fallback to M5 if timeframe not supported!
    # This was causing M5 data to show for M15/D1 when no data available
    if timeframe not in timeframe_dirs:
        logger.warning(f"⚠️  Unsupported timeframe: {timeframe}")
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    data_dir = timeframe_dirs[timeframe]

    # Special handling for D1 (Daily data from yearly universe files)
    if timeframe == "D1":
        logger.info(f"📅 Loading daily data for {symbol}")
        try:
            from ..data_loading.loaders.daily_data_loader import DailyDataLoader
            loader = DailyDataLoader()

            # Load last 100 days of daily data
            df = loader.load_data(symbol, days_back=100)

            if not df.empty:
                logger.info(f"✅ Loaded {len(df)} daily candles for {symbol}")
                return df
            else:
                logger.warning(f"⚠️  No daily data for {symbol}")
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        except Exception as e:
            logger.error(f"❌ Error loading daily data: {e}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # For intraday data (M1/M5/M15/H1), use parquet files
    parquet_path = TRADERUNNER_DIR / "artifacts" / data_dir / f"{symbol}.parquet"

    # If parquet file exists, don't generate mock data - return empty
    if parquet_path.exists():
        logger.info(f"📁 Found parquet for {symbol} {timeframe}: {parquet_path}")
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # CRITICAL: Never generate mock data for future dates
    if reference_date is not None:
        if isinstance(reference_date, str):
            reference_date = datetime.fromisoformat(reference_date).date()
        elif isinstance(reference_date, datetime):
            reference_date = reference_date.date()

        # Check if reference_date is in the future
        if isinstance(reference_date, date_type):
            if reference_date > datetime.now().date():
                logger.warning(f"Requested future date {reference_date}, returning empty")
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # If parquet file doesn't exist, return empty - NO MOCK DATA in production
    logger.info(f"❌ No parquet file for {symbol} - returning empty DataFrame")
    return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])


def generate_mock_candles(symbol: str, hours: int = 24, timeframe: str = "M5", reference_date = None) -> pd.DataFrame:
    """Generate mock candle data for development/testing."""
    import numpy as np
    from datetime import date as date_type

    # **CRITICAL**: Use deterministic seed so chart doesn't change on refresh
    # Seed based on symbol + current date (not time) so data is stable within same day
    seed = hash(symbol + datetime.now().strftime("%Y-%m-%d")) % (2**32)
    np.random.seed(seed)

    # Map timeframe to pandas frequency
    freq_map = {
        "M1": "1min",
        "M5": "5min",
        "M15": "15min",
        "H1": "1h"  # Use 'h' instead of deprecated 'H'
    }
    freq = freq_map.get(timeframe, "5min")

    # If reference_date provided, use it; otherwise use current datetime
    if reference_date is not None:
        if isinstance(reference_date, date_type):
            ref_datetime = datetime.combine(reference_date, datetime.min.time())
        else:
            ref_datetime = datetime.fromisoformat(str(reference_date))
    else:
        ref_datetime = datetime.now()

    # Check if reference date is a weekend (no trading)
    if ref_datetime.weekday() >= 5:  # Saturday=5, Sunday=6
        # Return empty DataFrame - no stock data on weekends
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # **US STOCK MARKET HOURS ONLY**
    # We only generate candles for actual US market session
    # Regular hours: 9:30-16:00 EST = 15:30-22:00 CET (6.5 hours)
    # Do NOT generate pre-market or after-hours for simplicity

    # Determine the trading day to use
    if ref_datetime.weekday() >= 5:
        # Weekend - no data
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # **CRITICAL FIX**: Create timestamps in Berlin timezone from the start
    # This prevents the +1 hour offset when converting from naive->UTC->Berlin
    import pytz
    berlin_tz = pytz.timezone('Europe/Berlin')

    # Create timezone-aware datetime for market session in Berlin time
    market_day_berlin = berlin_tz.localize(ref_datetime.replace(hour=15, minute=30, second=0, microsecond=0))

    # Market session times in CET (already timezone-aware)
    market_open = market_day_berlin.replace(hour=15, minute=30)  # 9:30 EST
    market_close = market_day_berlin.replace(hour=22, minute=0)  # 16:00 EST

    # Generate timestamps ONLY during market hours (timezone-aware from start)
    timestamps = pd.date_range(start=market_open, end=market_close, freq=freq, tz=berlin_tz)

    # Ensure we have at least some candles
    if len(timestamps) == 0:
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # Base price based on symbol (just for demo)
    base_prices = {
        "AAPL": 227.0,
        "MSFT": 450.0,
        "TSLA": 380.0,
        "NVDA": 140.0,
        "PLTR": 75.0,
    }
    open_price = base_prices.get(symbol, 100.0)

    # **CRITICAL FIX**: Generate deterministic closing price for the day
    # This ensures ALL timeframes (M1, M5, M15, H1) have the SAME close at 22:00
    # Use a separate seed based on symbol + date for daily close price
    close_seed = hash(symbol + ref_datetime.strftime("%Y-%m-%d") + "_close") % (2**32)
    np.random.seed(close_seed)

    # Generate realistic daily price movement (±2%)
    daily_change_pct = np.random.uniform(-0.02, 0.02)
    close_price = open_price * (1 + daily_change_pct)

    # Now generate intraday price path that goes from open to close
    num_candles = len(timestamps)

    # Reset seed for intraday movements
    np.random.seed(seed)

    # Create smooth price path from open to close
    # Use linear interpolation + random noise
    price_path = np.linspace(open_price, close_price, num_candles)

    # Add realistic intraday volatility (smaller than daily range)
    volatility = 0.005  # ±0.5% intraday noise
    noise = np.random.randn(num_candles) * open_price * volatility
    price_path = price_path + noise

    # Build OHLC data
    data = []
    for i, ts in enumerate(timestamps):
        # Current price point in path
        current = price_path[i]

        # Generate high/low around current price
        spread = abs(noise[i]) if noise[i] != 0 else open_price * 0.002
        high = current + abs(spread)
        low = current - abs(spread)

        # Open is previous close (or base for first candle)
        candle_open = data[-1]['close'] if i > 0 else open_price

        # Close is current price point (except last candle = daily close)
        candle_close = close_price if i == num_candles - 1 else current

        # Ensure OHLC consistency: L <= O,C <= H
        low = min(low, candle_open, candle_close)
        high = max(high, candle_open, candle_close)

        volume = int(np.random.uniform(100000, 1000000))

        data.append({
            'timestamp': ts,
            'open': candle_open,
            'high': high,
            'low': low,
            'close': candle_close,
            'volume': volume
        })

    # Convert list of dicts to DataFrame
    df = pd.DataFrame(data)

    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]


def check_live_data_availability(date=None) -> dict:
    """
    Fast lightweight check if live data exists for a date.

    Does NOT load actual candles - just checks if data exists.
    Much faster than loading full candles (< 100ms vs 30+ seconds).

    IMPORTANT: Only checks for symbols in strategy_deployments.yml (configured symbols),
    not all symbols in the database.

    Args:
        date: Date to check (default: today)

    Returns:
        {
            'available': bool,
            'symbol_count': int,
            'symbols': list[str],  # Configured symbols that have data
            'timeframes': list[str]
        }
    """
    from pathlib import Path
    from datetime import date as date_type
    import logging

    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("🔍 LIVE DATA AVAILABILITY CHECK STARTED")

    # Get configured symbols from strategy deployments
    from ..repositories import get_watchlist_symbols
    configured_symbols = get_watchlist_symbols()
    logger.info(f"📋 Configured symbols: {configured_symbols}")

    if not configured_symbols:
        logger.warning("❌ No configured symbols found")
        logger.info("=" * 80)
        return {'available': False, 'symbol_count': 0, 'symbols': [], 'timeframes': []}

    # Use central Settings for DB path
    settings = get_settings()
    db_path = settings.market_data_db_path

    if not db_path.exists():
        logger.warning(f"❌ market_data.db not found at: {db_path} - Returning unavailable")
        logger.info("=" * 80)
        return {'available': False, 'symbol_count': 0, 'symbols': [], 'timeframes': []}

    logger.info(f"📂 Using market_data DB: {db_path}")

    conn = None
    try:
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        logger.info(f"  ✅ Connected to: {db_path}")
    except Exception as e:
        logger.error(f"  ❌ Connection failed: {e}")

    if not conn:
        logger.warning("❌ NO DATABASE CONNECTION - Returning unavailable")
        logger.info("=" * 80)
        return {'available': False, 'symbol_count': 0, 'symbols': [], 'timeframes': []}

    try:
        query_date = date if date else date_type.today()
        logger.info(f"📅 Query date: {query_date} (type: {type(query_date)})")
        logger.info(f"📅 ISO format: {query_date.isoformat()}")

        # Query for configured symbols only
        placeholders = ','.join('?' * len(configured_symbols))
        query = f"""
            SELECT interval, symbol
            FROM candles
            WHERE symbol IN ({placeholders})
            AND DATE(timestamp/1000, 'unixepoch') = ?
            GROUP BY interval, symbol
            ORDER BY interval, symbol
        """

        params = tuple(configured_symbols) + (query_date.isoformat(),)
        logger.info(f"🔍 Executing query for symbols: {configured_symbols}")
        cursor = conn.execute(query, params)
        results = cursor.fetchall()

        logger.info(f"📊 Query results: {results}")
        logger.info(f"📊 Result count: {len(results)}")

        if results:
            # Get unique timeframes and symbols that have data
            timeframes = sorted(set(row[0] for row in results))
            symbols_with_data = sorted(set(row[1] for row in results))

            logger.info(f"✅ DATA AVAILABLE!")
            logger.info(f"  Symbols: {symbols_with_data} (count: {len(symbols_with_data)})")
            logger.info(f"  Timeframes: {timeframes}")
            logger.info("=" * 80)
            return {
                'available': True,
                'symbol_count': len(symbols_with_data),
                'symbols': symbols_with_data,
                'timeframes': timeframes
            }
        else:
            logger.warning(f"❌ NO RESULTS from query for date {query_date.isoformat()}")
            logger.info("=" * 80)
            return {'available': False, 'symbol_count': 0, 'symbols': [], 'timeframes': []}

    except Exception as e:
        logger.error(f"❌ ERROR in availability check: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.info("=" * 80)
        return {'available': False, 'symbol_count': 0, 'symbols': [], 'timeframes': []}
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed")


def get_live_candle_data(
    symbol: str,
    timeframe: str,
    date=None,
    limit: int = 500
) -> pd.DataFrame:
    """
    Get live candle data from marketdata.db (marketdata-stream service).

    This reads intraday candles that are actively being built from WebSocket ticks.
    Falls back gracefully if the database is not available.

    Args:
        symbol: Stock symbol
        timeframe: M1, M5, M15
        date: Date to query (default: today)
        limit: Max rows to return

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
        Empty DataFrame if no data or database unavailable
    """
    import logging
    from pathlib import Path
    from datetime import date as date_type

    logger = logging.getLogger(__name__)

    # Use central Settings for DB path
    from src.core.settings import get_settings
    settings = get_settings()
    configured_db_path = settings.market_data_db_path

    # Try to connect to marketdata.db
    db_paths = [
        Path("/opt/trading/marketdata-stream/data/market_data.db"),  # Production (correct filename!)
        configured_db_path # Local or configured path
    ]

    conn = None
    for db_path in db_paths:
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                logger.debug(f"Connected to marketdata.db at {db_path}")
                break
            except Exception as e:
                logger.warning(f"Could not connect to {db_path}: {e}")

    if not conn:
        logger.debug("marketdata.db not available - returning empty DataFrame")
        return pd.DataFrame()

    try:
        # Use today if no date specified
        query_date = date if date else date_type.today()

        # Convert timeframe to interval name in DB (M5 → M5, M1 → M1, etc.)
        interval = timeframe

        # Query candles for the specified date
        # timestamp is in milliseconds in the database
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol = ?
            AND interval = ?
            AND DATE(timestamp/1000, 'unixepoch') = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """

        df = pd.read_sql_query(
            query,
            conn,
            params=(symbol, interval, query_date.isoformat(), limit)
        )

        if not df.empty:
            # Convert timestamp from milliseconds to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            logger.info(f"📡 Loaded {len(df)} live candles for {symbol} {timeframe} on {query_date}")
        else:
            logger.debug(f"No live candles found for {symbol} {timeframe} on {query_date}")

        return df

    except Exception as e:
        logger.error(f"Error querying marketdata.db: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()
