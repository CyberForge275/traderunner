"""Session filtering for regular trading hours."""
from datetime import time, datetime
from typing import List
import pandas as pd
import pytz


class SessionFilter:
    """Filter candles to Regular Trading Hours (RTH) only."""
    
    RTH_START = time(9, 30)   # 9:30 AM ET
    RTH_END = time(16, 0)     # 4:00 PM ET
    ET_TZ = pytz.timezone('America/New_York')
    
    @classmethod
    def filter_to_rth(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter DataFrame to RTH candles only.
        
        Args:
            df: DataFrame with 'timestamp' column
            
        Returns:
            Filtered DataFrame with RTH candles only
            
        Raises:
            ValueError: If timestamp column missing or invalid
        """
        if 'timestamp' not in df.columns:
            raise ValueError("DataFrame must have 'timestamp' column")
        
        # Handle empty DataFrames
        if df.empty:
            return df.copy()
        
        # Ensure timezone-aware (convert to ET)
        df = df.copy()
        df['timestamp_et'] = pd.to_datetime(df['timestamp']).dt.tz_convert(cls.ET_TZ)
        
        # Filter: 9:30-16:00 ET, Monday-Friday only
        df['time'] = df['timestamp_et'].dt.time
        df['is_weekday'] = df['timestamp_et'].dt.dayofweek < 5
        
        mask = (
            (df['time'] >= cls.RTH_START) &
            (df['time'] < cls.RTH_END) &
            df['is_weekday']
        )
        
        # Clean up temporary columns
        result = df[mask].drop(columns=['timestamp_et', 'time', 'is_weekday'])
        
        return result.reset_index(drop=True)
    
    @classmethod
    def is_rth_time(cls, timestamp: datetime) -> bool:
        """Check if single timestamp is within RTH."""
        ts_et = timestamp.astimezone(cls.ET_TZ)
        t = ts_et.time()
        is_weekday = ts_et.weekday() < 5
        
        return (cls.RTH_START <= t < cls.RTH_END) and is_weekday
