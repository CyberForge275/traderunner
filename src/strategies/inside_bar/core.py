"""
InsideBar Strategy Core Logic - SINGLE SOURCE OF TRUTH

Critical: This module contains ALL pattern detection and signal generation logic.
It is used by BOTH backtesting and live trading adapters.

Zero-deviation requirement: Any change here must maintain 100% parity
between backtest and live trading results.

Version: 2.0.0
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import hashlib
import pandas as pd
import numpy as np

# Import SessionFilter from config module
from .config import SessionFilter


# ══════════════════════════════════════════════════════════════════════
# VERSION METADATA
# ══════════════════════════════════════════════════════════════════════

__version__ = "2.0.0"
__strategy_name__ = "InsideBar"


def _get_core_checksum() -> str:
    """
    Calculate SHA256 checksum of this core.py file.
    
    This ensures we can verify which exact version of the code
    generated a signal, even if version tags don't change.
    
    Returns:
        First 16 characters of SHA256 hash
    """
    try:
        core_path = Path(__file__)
        with open(core_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return "unknown"


STRATEGY_VERSION = __version__
STRATEGY_NAME = __strategy_name__
CORE_CHECKSUM = _get_core_checksum()


@dataclass
class InsideBarConfig:
    """
    Validated configuration for InsideBar strategy.
    
    This config is used by BOTH backtest and live trading.
    """
    # Core parameters (affect signal generation)
    atr_period: int = 14
    risk_reward_ratio: float = 2.0
    min_mother_bar_size: float = 0.5
    breakout_confirmation: bool = True
    inside_bar_mode: str = "inclusive"  # or "strict"
    
    # Session filtering (None = no filtering, applies to all time periods)
    session_filter: Optional[SessionFilter] = None
    
    # Live-specific parameters (ignored in backtest)
    lookback_candles: int = 50
    max_pattern_age_candles: int = 12
    max_deviation_atr: float = 3.0
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        assert self.atr_period > 0, "ATR period must be positive"
        assert self.risk_reward_ratio > 0, "Risk/reward ratio must be positive"
        assert self.min_mother_bar_size >= 0, "Min mother size must be non-negative"
        assert self.inside_bar_mode in ["inclusive", "strict"], \
            f"Invalid mode: {self.inside_bar_mode}"
    
    def __post_init__(self):
        """Auto-validate after initialization."""
        self.validate()


@dataclass
class RawSignal:
    """
    Raw signal output from core (format-agnostic).
    
    This is converted to specific formats by adapters:
    - Backtest: Signal object
    - Live: SignalOutputSpec
    """
    timestamp: pd.Timestamp
    side: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate signal data."""
        assert self.side in ["BUY", "SELL"], f"Invalid side: {self.side}"
        assert self.entry_price > 0, "Entry price must be positive"
        assert self.stop_loss > 0, "Stop loss must be positive"
        assert self.take_profit > 0, "Take profit must be positive"
        
        if self.side == "BUY":
            assert self.stop_loss < self.entry_price, \
                "BUY: Stop loss must be below entry"
            assert self.take_profit > self.entry_price, \
                "BUY: Take profit must be above entry"
        else:  # SELL
            assert self.stop_loss > self.entry_price, \
                "SELL: Stop loss must be above entry"
            assert self.take_profit < self.entry_price, \
                "SELL: Take profit must be below entry"


class InsideBarCore:
    """
    Core InsideBar strategy logic.
    
    Design Principles:
    1. Deterministic - same input always produces same output
    2. Stateless - no side effects
    3. Testable - pure functions
    4. Format-agnostic - returns raw data structures
    
    Usage:
        config = InsideBarConfig(atr_period=14, risk_reward_ratio=2.0)
        core = InsideBarCore(config)
        signals = core.process_data(df, symbol='APP')
    """
    
    def __init__(self, config: InsideBarConfig):
        """
        Initialize with validated config.
        
        Args:
            config: InsideBarConfig instance
        """
        config.validate()
        self.config = config
    
    @property
    def version(self) -> str:
        """Strategy version string."""
        return STRATEGY_VERSION
    
    @property
    def metadata(self) -> dict:
        """
        Strategy metadata including version and checksum.
        
        Returns:
            Dictionary with name, version, checksum, and file path
        """
        return {
            "name": STRATEGY_NAME,
            "version": STRATEGY_VERSION,
            "checksum": CORE_CHECKSUM,
            "file": __file__
        }
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Average True Range (ATR).
        
        ATR measures market volatility and is used for:
        1. Filtering minimum mother bar size
        2. Risk management (not directly, but informational)
        
        Args:
            df: DataFrame with columns: open, high, low, close
            
        Returns:
            DataFrame with added columns:
            - prev_close: Previous candle close
            - tr1, tr2, tr3: True Range components
            - true_range: Maximum of tr1, tr2, tr3
            - atr: Rolling average of true_range
        """
        df = df.copy()
        
        # Previous candle close (needed for TR calculation)
        df['prev_close'] = df['close'].shift(1)
        
        # True Range components:
        # TR1 = High - Low (current range)
        df['tr1'] = df['high'] - df['low']
        
        # TR2 = |High - Previous Close| (gap up)
        df['tr2'] = np.abs(df['high'] - df['prev_close'])
        
        # TR3 = |Low - Previous Close| (gap down)
        df['tr3'] = np.abs(df['low'] - df['prev_close'])
        
        # True Range = max(TR1, TR2, TR3)
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # ATR = Simple Moving Average of True Range
        df['atr'] = df['true_range'].rolling(
            window=self.config.atr_period,
            min_periods=self.config.atr_period
        ).mean()
        
        return df
    
    def detect_inside_bars(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect inside bar patterns.
        
        Inside Bar Definition:
        - Current candle's high is AT OR BELOW previous candle's high (inclusive mode)
        - Current candle's low is AT OR ABOVE previous candle's low (inclusive mode)
        - OR strictly inside (strict mode)
        
        Mother Bar:
        - The candle immediately before the inside bar
        - Its high and low define breakout levels
        
        Args:
            df: DataFrame with OHLC data and 'atr' column
            
        Returns:
            DataFrame with added columns:
            - prev_high: Previous candle high
            - prev_low: Previous candle low
            - prev_range: Previous candle range
            - is_inside_bar: Boolean mask
            - mother_bar_high: High of mother bar (NaN if not inside)
            - mother_bar_low: Low of mother bar (NaN if not inside)
        """
        df = df.copy()
        
        # Previous candle OHLC
        df['prev_high'] = df['high'].shift(1)
        df['prev_low'] = df['low'].shift(1)
        df['prev_range'] = df['prev_high'] - df['prev_low']
        
        # Inside bar condition based on mode
        if self.config.inside_bar_mode == "strict":
            # Strict: Current MUST be strictly inside (no touching)
            inside_mask = (
                (df['high'] < df['prev_high']) &
                (df['low'] > df['prev_low'])
            )
        else:  # inclusive (default)
            # Inclusive: Current can touch the previous high/low
            inside_mask = (
                (df['high'] <= df['prev_high']) &
                (df['low'] >= df['prev_low'])
            )
        
        # Ensure previous bar exists (not NaN)
        inside_mask = inside_mask & df['prev_high'].notna() & df['prev_low'].notna()
        
        # Optional: Minimum mother bar size filter
        # (avoid patterns where mother bar is too small/noisy)
        if self.config.min_mother_bar_size > 0:
            # Mother bar range must be >= min_mother_size * ATR
            size_ok = df['prev_range'] >= (
                self.config.min_mother_bar_size * df['atr']
            )
            inside_mask = inside_mask & size_ok.fillna(False)
        
        # Mark inside bars
        df['is_inside_bar'] = inside_mask
        
        # Store mother bar levels (only for inside bars, NaN otherwise)
        df['mother_bar_high'] = df['prev_high'].where(inside_mask)
        df['mother_bar_low'] = df['prev_low'].where(inside_mask)
        
        return df
    
    def generate_signals(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> List[RawSignal]:
        """
        Generate trading signals from inside bar patterns.
        
        Signal Generation Logic:
        1. Find inside bars in the data
        2. For each subsequent candle, check for breakout
        3. Breakout = price moves beyond mother bar high (LONG) or low (SHORT)
        4. Generate ONE signal per pattern (first breakout only)
        
        Args:
            df: DataFrame with inside bar detection results
                Must have: timestamp, close, high, low, is_inside_bar,
                          mother_bar_high, mother_bar_low, atr
            symbol: Trading symbol (e.g., 'APP')
            
        Returns:
            List of RawSignal objects (one per breakout)
        """
        signals = []
        
        # Check if we have any inside bars
        inside_mask = df['is_inside_bar'].fillna(False)
        if not inside_mask.any():
            return signals
        
        # Track which patterns have already generated signals
        # to avoid duplicates
        signaled_patterns = set()
        
        # Iterate through each candle (potential breakout)
        for idx in range(1, len(df)):
            current = df.iloc[idx]
            
            # Find the most recent inside bar BEFORE current candle
            recent_inside_bars = df.iloc[:idx][inside_mask[:idx]]
            
            if recent_inside_bars.empty:
                continue
            
            # Get the last (most recent) inside bar
            last_inside = recent_inside_bars.iloc[-1]
            last_inside_idx = recent_inside_bars.index[-1]
            
            # Skip if we already signaled this pattern
            if last_inside_idx in signaled_patterns:
                continue
            
            # Get mother bar breakout levels
            mother_high = last_inside['mother_bar_high']
            mother_low = last_inside['mother_bar_low']
            
            if pd.isna(mother_high) or pd.isna(mother_low):
                continue
            
            # Determine breakout price to compare
            if self.config.breakout_confirmation:
                # Conservative: Use close price (confirmed breakout)
                compare_high = current['close']
                compare_low = current['close']
            else:
                # Aggressive: Use high/low (intrabar breakout)
                compare_high = current['high']
                compare_low = current['low']
            
            # Check for LONG breakout (price breaks above mother high)
            if compare_high > mother_high:
                entry = float(mother_high)
                sl = float(mother_low)
                risk = entry - sl
                
                if risk <= 0:
                    continue
                
                tp = entry + (risk * self.config.risk_reward_ratio)
                
                signal = RawSignal(
                    timestamp=current['timestamp'],
                    side='BUY',
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    metadata={
                        'pattern': 'inside_bar_breakout',
                        'mother_high': float(mother_high),
                        'mother_low': float(mother_low),
                        'atr': float(current['atr']) if pd.notna(current['atr']) else 0.0,
                        'risk': risk,
                        'reward': risk * self.config.risk_reward_ratio,
                        'symbol': symbol
                    }
                )
                signals.append(signal)
                
                # Mark this pattern as signaled
                signaled_patterns.add(last_inside_idx)
            
            # Check for SHORT breakout (price breaks below mother low)
            elif compare_low < mother_low:
                entry = float(mother_low)
                sl = float(mother_high)
                risk = sl - entry
                
                if risk <= 0:
                    continue
                
                tp = entry - (risk * self.config.risk_reward_ratio)
                
                signal = RawSignal(
                    timestamp=current['timestamp'],
                    side='SELL',
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    metadata={
                        'pattern': 'inside_bar_breakout',
                        'mother_high': float(mother_high),
                        'mother_low': float(mother_low),
                        'atr': float(current['atr']) if pd.notna(current['atr']) else 0.0,
                        'risk': risk,
                        'reward': risk * self.config.risk_reward_ratio,
                        'symbol': symbol
                    }
                )
                signals.append(signal)
                
                # Mark this pattern as signaled
                signaled_patterns.add(last_inside_idx)
        
        return signals
    
    def process_data(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> List[RawSignal]:
        """
        Complete pipeline: Input data → Signals.
        
        This is the main entry point for both adapters.
        
        Pipeline:
        1. Validate input data
        2. Calculate ATR
        3. Detect inside bars
        4. Generate breakout signals
        5. Apply session filtering (if configured)
        
        Args:
            df: DataFrame with OHLC data
                Required columns: timestamp, open, high, low, close
                Optional: volume
            symbol: Trading symbol
            
        Returns:
            List of RawSignal objects (filtered by session if configured)
            
        Raises:
            ValueError: If required columns are missing
        """
        # Validate required columns
        required = ['timestamp', 'open', 'high', 'low', 'close']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Ensure DataFrame is sorted by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Pipeline: Calculate ATR, detect patterns, generate signals
        df = self.calculate_atr(df)
        df = self.detect_inside_bars(df)
        signals = self.generate_signals(df, symbol)
        
        # Apply session filtering if configured
        if self.config.session_filter is not None:
            filtered_signals = []
            for sig in signals:
                # Ensure timestamp is a pd.Timestamp
                ts = pd.to_datetime(sig.timestamp)
                if self.config.session_filter.is_in_session(ts):
                    filtered_signals.append(sig)
            return filtered_signals
        
        return signals
