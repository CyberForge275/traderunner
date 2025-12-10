"""
Candle data retrieval for charts
"""
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

from ..config import MARKETDATA_DIR


def get_candle_data(symbol: str, timeframe: str = "M5", hours: int = 24, reference_date = None) -> pd.DataFrame:
    """
    Get candle data for charting.
    
    Args:
        symbol: Stock symbol  
        timeframe: M1, M5, M15, H1
        hours: Hours of history to fetch
        reference_date: Specific date to fetch data for (date object or None for current)
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
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
            "H1": "data_m5"  # Use M5 data for H1 (will resample)
        }
        
        data_dir = timeframe_dirs.get(timeframe, "data_m5")
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
            
            # Filter by reference_date if provided
            if reference_date is not None:
                from datetime import date as date_type, datetime
                if isinstance(reference_date, date_type):
                    ref_date = reference_date
                else:
                    ref_date = datetime.fromisoformat(str(reference_date)).date()
                
                # Filter to only this date
                df = df[df['timestamp'].dt.date == ref_date]
            
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
    
    timeframe_dirs = {
        "M1": "data_m1",
        "M5": "data_m5", 
        "M15": "data_m15",
        "H1": "data_m5"
    }
    data_dir = timeframe_dirs.get(timeframe, "data_m5")
    parquet_path = TRADERUNNER_DIR / "artifacts" / data_dir / f"{symbol}.parquet"
    
    # If parquet file exists, don't generate mock data - return empty
    if parquet_path.exists():
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # CRITICAL: Never generate mock data for future dates
    if reference_date is not None:
        if isinstance(reference_date, str):
            ref_date = datetime.fromisoformat(reference_date).date()
        elif isinstance(reference_date, date_type):
            ref_date = reference_date
        else:
            ref_date = reference_date.date() if hasattr(reference_date, 'date') else None
        
        # Check if date is in the future
        if ref_date and ref_date > date_type.today():
            print(f"Requested future date {ref_date} for {symbol} - returning empty")
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
