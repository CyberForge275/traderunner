"""
Backtesting Data Catalog - Reports data availability and health.

CRITICAL ARCHITECTURE RULES:
- Parquet-only: M1/M5/M15 files, D1 universe
- No sqlite3, no live data sources
- Performance: fast file checks, lazy dataframe loads
"""

from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import pandas as pd
import logging

from axiom_bt.fs import DATA_M1, DATA_M5, DATA_M15
from trading_dashboard.repositories.daily_universe import DailyUniverseRepository

logger = logging.getLogger(__name__)


@dataclass
class TimeframeInfo:
    """Info about data availability for a timeframe."""
    exists: bool
    derivable: bool = False
    rows: int = 0
    first_date: Optional[pd.Timestamp] = None
    last_date: Optional[pd.Timestamp] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class BacktestingDataCatalog:
    """
    Report data availability and health for backtesting.
    
    Checks:
    - File existence (M1/M5/M15 parquet, D1 universe)
    - Date ranges, row counts, last timestamp
    - Fragmentation/gaps detection
    - Derivability (H1 from M5/M1)
    
    Output: Dict per symbol with timeframe status
    """
    
    def __init__(self, universe_path: Optional[Path] = None):
        """
        Initialize catalog.
        
        Args:
            universe_path: Optional custom universe parquet path
        """
        self.daily_repo = DailyUniverseRepository(universe_path=universe_path)
    
    def get_symbol_info(self, symbol: str) -> Dict[str, TimeframeInfo]:
        """
        Get complete availability info for a symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dict mapping timeframe (M1/M5/M15/H1/D1) to TimeframeInfo
        """
        symbol = symbol.strip().upper()
        
        info = {}
        
        # Check intraday timeframes
        for tf, path_base in [('M1', DATA_M1), ('M5', DATA_M5), ('M15', DATA_M15)]:
            info[tf] = self._check_intraday(symbol, tf, path_base)
        
        # Check H1 (derivable)
        info['H1'] = self._check_h1(symbol, info['M1'], info['M5'])
        
        # Check D1 (universe)
        info['D1'] = self._check_daily(symbol)
        
        return info
    
    def _check_intraday(
        self, 
        symbol: str, 
        timeframe: str, 
        path_base: Path
    ) -> TimeframeInfo:
        """Check intraday parquet file availability."""
        file_path = path_base / f"{symbol}.parquet"
        
        if not file_path.exists():
            return TimeframeInfo(exists=False)
        
        try:
            # Read parquet to get stats
            df = pd.read_parquet(file_path)
            
            if df.empty:
                return TimeframeInfo(
                    exists=True,
                    rows=0,
                    warnings=["File exists but contains no data"]
                )
            
            # Extract info
            if isinstance(df.index, pd.DatetimeIndex):
                first_date = df.index.min()
                last_date = df.index.max()
            else:
                # Has timestamp column
                first_date = df['timestamp'].min() if 'timestamp' in df.columns else None
                last_date = df['timestamp'].max() if 'timestamp' in df.columns else None
            
            warnings = []
            
            # Check for gaps (simple heuristic: expected days vs actual rows)
            if first_date and last_date:
                days_span = (last_date - first_date).days + 1
                expected_bars_per_day = {
                    'M1': 390,  # 6.5 hours * 60 min
                    'M5': 78,   # 6.5 hours * 12 bars/hour
                    'M15': 26   # 6.5 hours * 4 bars/hour
                }
                expected = days_span * expected_bars_per_day.get(timeframe, 1)
                if len(df) < expected * 0.5:  # Less than 50% of expected
                    warnings.append(f"Potential gaps: {len(df)} bars vs ~{expected} expected")
            
            return TimeframeInfo(
                exists=True,
                rows=len(df),
                first_date=first_date,
                last_date=last_date,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Error checking {symbol} {timeframe}: {e}")
            return TimeframeInfo(
                exists=True,
                warnings=[f"Error reading file: {str(e)[:50]}"]
            )
    
    def _check_h1(
        self, 
        symbol: str, 
        m1_info: TimeframeInfo, 
        m5_info: TimeframeInfo
    ) -> TimeframeInfo:
        """Check if H1 can be derived from M5 or M1."""
        if m5_info.exists:
            return TimeframeInfo(
                exists=False,
                derivable=True,
                warnings=["Can be resampled from M5"]
            )
        elif m1_info.exists:
            return TimeframeInfo(
                exists=False,
                derivable=True,
                warnings=["Can be resampled from M1 (slower)"]
            )
        else:
            return TimeframeInfo(
                exists=False,
                derivable=False,
                warnings=["Cannot derive: M1 and M5 both missing"]
            )
    
    def _check_daily(self, symbol: str) -> TimeframeInfo:
        """Check daily data from universe."""
        try:
            has_symbol = self.daily_repo.has_symbol(symbol)
            
            if not has_symbol:
                return TimeframeInfo(
                    exists=False,
                    warnings=[f"{symbol} not found in universe"]
                )
            
            # Get date range
            first_date, last_date = self.daily_repo.get_date_range(symbol)
            
            if first_date is None or last_date is None:
                return TimeframeInfo(
                    exists=True,
                    warnings=["Symbol exists but no date range available"]
                )
            
            # Load to get row count (cached)
            df = self.daily_repo.load_symbol(symbol)
            
            return TimeframeInfo(
                exists=True,
                rows=len(df),
                first_date=first_date,
                last_date=last_date,
                warnings=[]
            )
            
        except Exception as e:
            logger.error(f"Error checking {symbol} D1: {e}")
            return TimeframeInfo(
                exists=False,
                warnings=[f"Error checking universe: {str(e)[:50]}"]
            )
    
    def get_available_timeframes(self, symbol: str) -> List[str]:
        """
        Get list of available (or derivable) timeframes for symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            List of timeframe strings (e.g., ['M5', 'D1', 'H1'])
        """
        info = self.get_symbol_info(symbol)
        available = []
        
        for tf, tf_info in info.items():
            if tf_info.exists or tf_info.derivable:
                available.append(tf)
        
        return sorted(available)
    
    def get_warnings(self, symbol: str) -> List[str]:
        """
        Get all warnings for a symbol across all timeframes.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            List of warning strings
        """
        info = self.get_symbol_info(symbol)
        warnings = []
        
        for tf, tf_info in info.items():
            for warning in tf_info.warnings:
                warnings.append(f"{tf}: {warning}")
        
        return warnings
    
    def is_date_in_range(
        self, 
        symbol: str, 
        timeframe: str, 
        target_date: pd.Timestamp
    ) -> bool:
        """
        Check if a date falls within available data range.
        
        Args:
            symbol: Stock symbol
            timeframe: M1/M5/M15/H1/D1
            target_date: Date to check
        
        Returns:
            True if date is in range
        """
        info = self.get_symbol_info(symbol)
        tf_info = info.get(timeframe)
        
        if not tf_info or not (tf_info.exists or tf_info.derivable):
            return False
        
        if tf_info.first_date is None or tf_info.last_date is None:
            return False
        
        target_date = pd.Timestamp(target_date)
        return tf_info.first_date <= target_date <= tf_info.last_date
    
    def get_nearest_date(
        self, 
        symbol: str, 
        timeframe: str, 
        target_date: pd.Timestamp
    ) -> Optional[pd.Timestamp]:
        """
        Get nearest available date if target is out of range.
        
        Args:
            symbol: Stock symbol
            timeframe: M1/M5/M15/H1/D1
            target_date: Target date
        
        Returns:
            Nearest available date or None
        """
        info = self.get_symbol_info(symbol)
        tf_info = info.get(timeframe)
        
        if not tf_info or not (tf_info.exists or tf_info.derivable):
            return None
        
        if tf_info.first_date is None or tf_info.last_date is None:
            return None
        
        target_date = pd.Timestamp(target_date)
        
        if target_date < tf_info.first_date:
            return tf_info.first_date
        elif target_date > tf_info.last_date:
            return tf_info.last_date
        else:
            return target_date
