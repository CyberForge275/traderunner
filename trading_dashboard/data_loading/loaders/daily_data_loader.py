"""
Daily Data Loader for Trading Strategies

Loads daily (D1) OHLCV data from yearly parquet files.
Data is updated daily at 4:00 AM from MySQL database.

Architecture:
- Yearly split: one file per year (e.g., universe_2025.parquet)
- Size: ~40MB per year
- Fast loading and filtering
- Auto-detection of available years
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Union, List
import logging


logger = logging.getLogger(__name__)


class DailyDataLoader:
    """
    Loader for daily (D1) candle data from yearly parquet files.
    
    Features:
    - Yearly split files (universe_YYYY.parquet)
    - Fast symbol filtering
    - Date range queries
    - Auto-detection of available data
    
    Example:
        loader = DailyDataLoader()
        
        # Load single symbol
        df = loader.load_data('AAPL', days_back=100)
        
        # Load multiple symbols
        df = loader.load_data(['AAPL', 'TSLA'], 
                               start_date='2024-01-01',
                               end_date='2024-12-31')
    """
    
    def _get_data_dir(self) -> Path:
        """Get D1 data directory from central Settings."""
        from src.core.settings import get_settings
        settings = get_settings()
        data_dir = settings.data_d1_dir
        
        # Ensure directory exists
        if not data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created D1 data directory: {data_dir}")
        
        return data_dir
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize daily data loader.
        
        Args:
            data_dir: Directory containing universe_YYYY.parquet files
                     Auto-detects if None
        """
        if data_dir is None:
            # Auto-detect data directory using Settings
            self.data_dir = self._get_data_dir()
        else:
            self.data_dir = Path(data_dir)
        
        logger.info(f"DailyDataLoader initialized: {self.data_dir}")
        
        # Cache for loaded data
        self._cache = {}
    
    def load_data(
        self,
        symbols: Union[str, List[str]],
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        days_back: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load daily data for symbol(s).
        
        Args:
            symbols: Single symbol or list of symbols
            start_date: Start date (inclusive)
            end_date: End date (inclusive) 
            days_back: Alternative to start_date - load N days back from today
            
        Returns:
            DataFrame with columns: timestamp, symbol, open, high, low, close, volume
            Sorted by timestamp (oldest first)
            
        Example:
            # Last 100 days for AAPL
            df = loader.load_data('AAPL', days_back=100)
            
            # Specific date range
            df = loader.load_data(['AAPL', 'TSLA'], 
                                   start_date='2024-01-01',
                                   end_date='2024-12-31')
        """
        # Normalize symbols to list
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # Parse dates
        if days_back is not None:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
        else:
            if start_date is None:
                start_date = datetime(2020, 1, 1)  # Default: 5 years back
            if end_date is None:
                end_date = datetime.now()
            
            if isinstance(start_date, str):
                start_date = pd.to_datetime(start_date)
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)
        
        # Determine which years to load
        years = range(start_date.year, end_date.year + 1)
        
        # Load data for each year
        dfs = []
        for year in years:
            year_df = self._load_year(year)
            if year_df is not None and not year_df.empty:
                dfs.append(year_df)
        
        if not dfs:
            logger.warning(f"No data found for {symbols} in range {start_date} to {end_date}")
            return pd.DataFrame()
        
        # Concatenate all years
        df = pd.concat(dfs, ignore_index=True)
        
        # Filter by symbols
        df = df[df['symbol'].isin(symbols)]
        
        # Filter by date range
        df = df[
            (df['timestamp'] >= start_date) &
            (df['timestamp'] <= end_date)
        ]
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(
            f"Loaded {len(df)} daily candles for {len(symbols)} symbols "
            f"({start_date.date()} to {end_date.date()})"
        )
        
        return df
    
    def _load_year(self, year: int) -> Optional[pd.DataFrame]:
        """
        Load data for a specific year.
        
        Args:
            year: Year to load (e.g., 2025)
            
        Returns:
            DataFrame with all symbols for that year, or None if not found
        """
        # Check cache first
        if year in self._cache:
            return self._cache[year]
        
        # Build file path
        file_path = self.data_dir / f'universe_{year}.parquet'
        
        if not file_path.exists():
            logger.debug(f"Year {year} file not found: {file_path}")
            return None
        
        try:
            df = pd.read_parquet(file_path)
            
            # Normalize column names (handle different formats)
            df.columns = [c.lower() for c in df.columns]
            
            # Ensure timestamp column exists
            if 'timestamp' not in df.columns and df.index.name in ['timestamp', 'date']:
                df = df.reset_index()
                df = df.rename(columns={df.index.name: 'timestamp'})
            
            # Ensure timestamp is datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Ensure symbol column exists
            if 'symbol' not in df.columns:
                logger.warning(f"No 'symbol' column in {file_path}")
                return None
            
            # Cache the data
            self._cache[year] = df
            
            logger.debug(f"Loaded year {year}: {len(df)} rows, {df['symbol'].nunique()} symbols")
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None
    
    def get_available_symbols(self, year: Optional[int] = None) -> List[str]:
        """
        Get list of available symbols.
        
        Args:
            year: Specific year to check (current year if None)
            
        Returns:
            Sorted list of available symbols
        """
        if year is None:
            year = datetime.now().year
        
        df = self._load_year(year)
        
        if df is None or df.empty:
            return []
        
        return sorted(df['symbol'].unique().tolist())
    
    def get_available_years(self) -> List[int]:
        """
        Get list of years with available data.
        
        Returns:
            Sorted list of years
        """
        files = list(self.data_dir.glob('universe_*.parquet'))
        years = []
        
        for file in files:
            try:
                year = int(file.stem.split('_')[1])
                years.append(year)
            except (IndexError, ValueError):
                continue
        
        return sorted(years)
    
    def get_latest_update(self, year: Optional[int] = None) -> Optional[datetime]:
        """
        Get timestamp of latest data update.
        
        Args:
            year: Year to check (current year if None)
            
        Returns:
            Datetime of most recent data point, or None
        """
        if year is None:
            year = datetime.now().year
        
        df = self._load_year(year)
        
        if df is None or df.empty:
            return None
        
        return df['timestamp'].max()
    
    def clear_cache(self):
        """Clear cached data to free memory."""
        self._cache = {}
        logger.info("Cache cleared")
