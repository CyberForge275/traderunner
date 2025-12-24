"""
Unified Data Adapter
Routes candle data requests to appropriate source based on context.

Data Sources:
- Live/Today: market_data.db (websocket tick aggregations)
- Historic: Parquet files (backtesting data)
- Test: Parquet files (mock/synthetic data)

Strategy:
1. Check date: today → try database first
2. Historic date → parquet only
3. Fallback: database → parquet → empty
"""

import pandas as pd
from datetime import date, datetime
from pathlib import Path
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CandleDataAdapter:
    """
    Intelligent candle data adapter that routes requests to the appropriate source.
    
    Rules:
    - Today's date: Load from market_data.db (live websocket data)
    - Historic dates: Load from parquet files (backtesting/mock data)
    - Fallback: Try both sources, merge if necessary
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.CandleDataAdapter")
    
    def get_candles(
        self,
        symbol: str,
        timeframe: str = "M5",
        reference_date: Optional[date] = None,
        hours: int = 24,
        limit: int = 500
    ) -> pd.DataFrame:
        """
        Get candle data from the appropriate source based on context.
        
        Args:
            symbol: Stock symbol
            timeframe: Candle interval (M1, M5, M15, H1)
            reference_date: Date to get data for (default: today)
            hours: Hours of data to retrieve
            limit: Maximum candles to return
            
        Returns:
            DataFrame with candle data (may be empty)
        """
        if reference_date is None:
            reference_date = date.today()
        
        self.logger.info(f"📊 Fetching {symbol} {timeframe} for {reference_date}")
        
        # Determine strategy based on date
        is_today = reference_date == date.today()
        
        if is_today:
            self.logger.info("   Context: TODAY → trying database (websocket data)")
            df = self._get_from_database(symbol, timeframe, reference_date, limit)
            
            if not df.empty:
                self.logger.info(f"   ✅ Loaded {len(df)} candles from database")
                return df
            
            self.logger.info("   Database empty, trying parquet fallback...")
            df = self._get_from_parquet(symbol, timeframe, reference_date, hours)
            
            if not df.empty:
                self.logger.info(f"   ✅ Loaded {len(df)} candles from parquet (fallback)")
            else:
                self.logger.warning(f"   ❌ No data found in database or parquet for {symbol}")
            
            return df
        else:
            self.logger.info("   Context: HISTORIC → loading from parquet")
            df = self._get_from_parquet(symbol, timeframe, reference_date, hours)
            
            if not df.empty:
                self.logger.info(f"   ✅ Loaded {len(df)} candles from parquet")
            else:
                self.logger.warning(f"   ❌ No parquet data for {symbol} on {reference_date}")
            
            return df
    
    def _get_from_database(
        self,
        symbol: str,
        timeframe: str,
        query_date: date,
        limit: int = 500
    ) -> pd.DataFrame:
        """Load candles from market_data.db (websocket source)."""
        try:
            from .candles import get_live_candle_data
            return get_live_candle_data(symbol, timeframe, query_date, limit)
        except Exception as e:
            self.logger.error(f"   Error loading from database: {e}")
            return pd.DataFrame()
    
    def _get_from_parquet(
        self,
        symbol: str,
        timeframe: str,
        reference_date: date,
        hours: int = 24
    ) -> pd.DataFrame:
        """Load candles from parquet files (historic/backtesting source)."""
        try:
            from .candles import get_candle_data
            return get_candle_data(symbol, timeframe, hours, reference_date)
        except Exception as e:
            self.logger.error(f"   Error loading from parquet: {e}")
            return pd.DataFrame()
    
    def get_availability_info(self, query_date: Optional[date] = None) -> dict:
        """
        Check which data sources are available for a given date.
        
        Returns:
            dict with 'database' and 'parquet' availability info
        """
        if query_date is None:
            query_date = date.today()
        
        result = {
            'date': query_date,
            'is_today': query_date == date.today(),
            'database_available': False,
            'parquet_available': False,
            'recommended_source': None
        }
        
        # Check database (only for today)
        if result['is_today']:
            try:
                from .candles import check_live_data_availability
                db_check = check_live_data_availability(query_date)
                result['database_available'] = db_check['available']
                result['database_symbols'] = db_check.get('symbols', [])
                result['database_timeframes'] = db_check.get('timeframes', [])
            except Exception as e:
                self.logger.error(f"Error checking database: {e}")
        
        # Check parquet (always check for fallback)
        # Note: This would need implementation in candles.py
        # For now, we'll assume parquet might be available
        result['parquet_available'] = True  # Simplified
        
        # Determine recommendation
        if result['is_today'] and result['database_available']:
            result['recommended_source'] = 'database'
        elif result['parquet_available']:
            result['recommended_source'] = 'parquet'
        else:
            result['recommended_source'] = None
        
        return result


# Singleton instance for easy access
_adapter_instance = None

def get_data_adapter() -> CandleDataAdapter:
    """Get the singleton data adapter instance."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = CandleDataAdapter()
    return _adapter_instance
