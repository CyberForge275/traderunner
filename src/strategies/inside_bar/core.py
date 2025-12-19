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
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from pathlib import Path
import hashlib
import pandas as pd
import numpy as np

# Import config classes from config module
from .config import SessionFilter, InsideBarConfig


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
        symbol: str,
        tracer: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[RawSignal]:
        """
        Generate trading signals with First-IB-per-session semantics.
        
        SPEC: Only the FIRST inside bar per session is traded.
        This is implemented via a session state machine.
        
        Args:
            df: DataFrame with inside bar detection results
                Must have: timestamp, close, high, low, is_inside_bar,
                          mother_bar_high, mother_bar_low, atr
            symbol: Trading symbol (e.g., 'TSLA')
            tracer: Optional callback for debugging/audit trail
            
        Returns:
            List of RawSignal objects
        """
        signals: List[RawSignal] = []

        def emit(event: Dict[str, Any]) -> None:
            if tracer is not None:
                tracer(event)

        # Get session configuration
        session_filter = self.config.session_filter
        if session_filter is None:
            # No session filtering - process all bars
            session_filter = SessionFilter(windows=[])
        
        session_tz = getattr(self.config, 'session_timezone', 'Europe/Berlin')
        
        # DEBUG: Log session filter configuration
        emit({
            'event': 'session_filter_config',
            'session_tz': session_tz,
            'session_windows': session_filter.to_strings() if session_filter and hasattr(session_filter, 'to_strings') else 'empty',
            'windows_count': len(session_filter.windows) if session_filter else 0
        })
        
        # Session state machine: {session_key: state_dict}
        session_states: Dict[tuple, Dict[str, Any]] = {}
        
        # Additional hard limit counter (belt-and-suspenders with state machine)
        signals_per_session: Dict[tuple, int] = {}
        max_trades = getattr(self.config, 'max_trades_per_session', 1)
        
        # Entry level mode
        entry_mode = getattr(self.config, 'entry_level_mode', 'mother_bar')
        
        # SL cap parameters
        sl_cap_ticks = getattr(self.config, 'stop_distance_cap_ticks', 40)
        tick_size = getattr(self.config, 'tick_size', 0.01)
        max_risk = sl_cap_ticks * tick_size
        
        # Check if we have any inside bars
        inside_mask = df["is_inside_bar"].fillna(False)
        if not inside_mask.any():
            emit({"event": "no_inside_bars", "rows": int(len(df))})
            return signals
        
        # Iterate bars starting from index 1 (need previous bar)
        for idx in range(1, len(df)):
            current = df.iloc[idx]
            prev = df.iloc[idx - 1]
            
            # === TIMESTAMP VALIDATION ===
            ts = pd.to_datetime(current['timestamp'])
            prev_ts = pd.to_datetime(prev['timestamp'])
            
            if ts.tz is None or prev_ts.tz is None:
                emit({
                    'event': 'signal_rejected',
                    'reason': 'naive_timestamp',
                    'idx': int(idx),
                    'ts': str(ts) if ts.tz is None else None,
                    'prev_ts': str(prev_ts) if prev_ts.tz is None else None
                })
                continue
            
            # === SESSION GATE ===
            # Both current and prev must be in sessions (but can be different sessions)
            try:
                session_idx = session_filter.get_session_index(ts, session_tz)
                prev_session_idx = session_filter.get_session_index(prev_ts, session_tz)
            except ValueError as e:
                # SessionFilter raises ValueError for naive timestamps
                emit({
                    'event': 'signal_rejected',
                    'reason': 'session_filter_error',
                    'idx': int(idx),
                    'error': str(e)
                })
                continue
            
            # DEBUG: Log session gate check
            emit({
                'event': 'session_gate_check',
                'idx': int(idx),
                'ts': ts.isoformat(),
                'ts_local': ts.tz_convert(session_tz).strftime('%H:%M'),
                'session_idx': session_idx,
                'prev_session_idx': prev_session_idx
            })
            
            if session_idx is None:
                # Current bar outside session - skip
                emit({
                    'event': 'bar_rejected_outside_session',
                    'idx': int(idx),
                    'ts': ts.isoformat(),
                    'ts_local': ts.tz_convert(session_tz).strftime('%H:%M')
                })
                continue
            
            # Build session key
            ts_session = ts.tz_convert(session_tz)
            session_key = (ts_session.date(), session_idx)
            
            # Initialize session state if new
            if session_key not in session_states:
                session_states[session_key] = {
                    'armed': False,
                    'done': False,
                    'ib_idx': None,
                    'levels': {}
                }
            
            state = session_states[session_key]
            
            # === STATE: DONE (already traded this session) ===
            if state['done']:
                continue
            
            # === STATE: SEARCH FOR FIRST IB ===
            if not state['armed']:
                # Check if current bar is inside bar AND mother bar is in SAME session
                if prev_session_idx != session_idx:
                    # Mother bar outside current session - cannot use
                    emit({
                        'event': 'ib_rejected',
                        'reason': 'mother_bar_outside_session',
                        'idx': int(idx),
                        'current_session': session_idx,
                        'prev_session': prev_session_idx,
                        'session_key': str(session_key)
                    })
                    continue
                
                # Check IB condition (inclusive mode)
                is_inside = (
                    current['high'] <= prev['high'] and 
                    current['low'] >= prev['low']
                )
                
                if is_inside:
                    # Check min mother bar size
                    mother_range = prev['high'] - prev['low']
                    atr_val = current['atr'] if 'atr' in current and pd.notna(current['atr']) else 0.0
                    min_size = self.config.min_mother_bar_size * atr_val
                    
                    if mother_range < min_size:
                        emit({
                            'event': 'ib_rejected',
                            'reason': 'mother_bar_too_small',
                            'idx': int(idx),
                            'mother_range': float(mother_range),
                            'min_size': float(min_size),
                            'atr': float(atr_val)
                        })
                        continue
                    
                    # FIRST IB FOUND - ARM SESSION
                    state['armed'] = True
                    state['ib_idx'] = idx
                    state['levels'] = {
                        'mother_high': float(prev['high']),
                        'mother_low': float(prev['low']),
                        'ib_high': float(current['high']),
                        'ib_low': float(current['low']),
                        'atr': float(atr_val)
                    }
                    
                    emit({
                        'event': 'ib_armed',
                        'session_key': str(session_key),
                        'ib_idx': int(idx),
                        'ib_ts': ts.isoformat(),
                        'levels': state['levels']
                    })
                    continue
            
            # === STATE: ARMED (watch for breakout of THE FIRST IB) ===
            if state['armed'] and not state['done']:
                levels = state['levels']
                
                # Determine entry levels based on entry_level_mode
                if entry_mode == "mother_bar":
                    entry_long = levels['mother_high']
                    entry_short = levels['mother_low']
                else:  # inside_bar
                    entry_long = levels['ib_high']
                    entry_short = levels['ib_low']
                
                # === MAX TRADES CHECK (hard limit) ===
                if signals_per_session.get(session_key, 0) >= max_trades:
                    emit({
                        'event': 'signal_rejected',
                        'reason': 'max_trades_reached',
                        'session_key': str(session_key),
                        'count': signals_per_session[session_key]
                    })
                    state['done'] = True  # Mark session done
                    continue
                
                # Check LONG breakout
                if current['close'] > entry_long:
                    # Calculate SL with cap
                    sl = levels['mother_low']
                    initial_risk = entry_long - sl
                    
                    if initial_risk <= 0:
                        emit({
                            'event': 'signal_rejected',
                            'reason': 'non_positive_risk',
                            'idx': int(idx),
                            'entry': entry_long,
                            'sl': sl
                        })
                        continue
                    
                    # === SL CAP ===
                    effective_risk = initial_risk
                    stop_cap_applied = False
                    
                    if initial_risk > max_risk:
                        sl = entry_long - max_risk
                        effective_risk = max_risk
                        stop_cap_applied = True
                    
                    tp = entry_long + (effective_risk * self.config.risk_reward_ratio)
                    
                    signal = RawSignal(
                        timestamp=ts,
                        side='BUY',
                        entry_price=entry_long,
                        stop_loss=sl,
                        take_profit=tp,
                        metadata={
                            'pattern': 'inside_bar_breakout',
                            'session_key': str(session_key),
                            'ib_idx': state['ib_idx'],
                            'entry_mode': entry_mode,
                            'stop_cap_applied': stop_cap_applied,
                            'initial_risk': initial_risk,
                            'effective_risk': effective_risk,
                            'mother_high': levels['mother_high'],
                            'mother_low': levels['mother_low'],
                            'atr': levels['atr'],
                            'symbol': symbol
                        }
                    )
                    signals.append(signal)
                    state['done'] = True
                    signals_per_session[session_key] = signals_per_session.get(session_key, 0) + 1
                    
                    emit({
                        'event': 'signal_generated',
                        'side': 'BUY',
                        'session_key': str(session_key),
                        'entry': entry_long,
                        'sl': sl,
                        'tp': tp,
                        'stop_cap_applied': stop_cap_applied
                    })
                    
                # Check SHORT breakout
                elif current['close'] < entry_short:
                    # Calculate SL with cap
                    sl = levels['mother_high']
                    initial_risk = sl - entry_short
                    
                    if initial_risk <= 0:
                        emit({
                            'event': 'signal_rejected',
                            'reason': 'non_positive_risk',
                            'idx': int(idx),
                            'entry': entry_short,
                            'sl': sl
                        })
                        continue
                    
                    # === SL CAP ===
                    effective_risk = initial_risk
                    stop_cap_applied = False
                    
                    if initial_risk > max_risk:
                        sl = entry_short + max_risk
                        effective_risk = max_risk
                        stop_cap_applied = True
                    
                    tp = entry_short - (effective_risk * self.config.risk_reward_ratio)
                    
                    signal = RawSignal(
                        timestamp=ts,
                        side='SELL',
                        entry_price=entry_short,
                        stop_loss=sl,
                        take_profit=tp,
                        metadata={
                            'pattern': 'inside_bar_breakout',
                            'session_key': str(session_key),
                            'ib_idx': state['ib_idx'],
                            'entry_mode': entry_mode,
                            'stop_cap_applied': stop_cap_applied,
                            'initial_risk': initial_risk,
                            'effective_risk': effective_risk,
                            'mother_high': levels['mother_high'],
                            'mother_low': levels['mother_low'],
                            'atr': levels['atr'],
                            'symbol': symbol
                        }
                    )
                    signals.append(signal)
                    state['done'] = True
                    signals_per_session[session_key] = signals_per_session.get(session_key, 0) + 1
                    
                    emit({
                        'event': 'signal_generated',
                        'side': 'SELL',
                        'session_key': str(session_key),
                        'entry': entry_short,
                        'sl': sl,
                        'tp': tp,
                        'stop_cap_applied': stop_cap_applied
                    })

        return signals
    
    def process_data(
        self,
        df: pd.DataFrame,
        symbol: str,
        tracer: Optional[Callable[[Dict[str, Any]], None]] = None,
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
        signals = self.generate_signals(df, symbol, tracer=tracer)
        
        # Apply session filtering if configured
        if self.config.session_filter is not None:
            session_tz = getattr(self.config, 'session_timezone', None) or "Europe/Berlin"
            
            # DEBUG: Log final filter application
            if tracer:
                tracer({
                    'event': 'final_filter_apply',
                    'signals_before': len(signals),
                    'session_tz': session_tz,
                    'session_windows': self.config.session_filter.to_strings()
                })
            
            filtered_signals = []
            for sig in signals:
                # Ensure timestamp is a pd.Timestamp
                ts = pd.to_datetime(sig.timestamp)
                in_session = self.config.session_filter.is_in_session(ts, session_tz)
                
                # DEBUG: Log each filter decision
                if tracer:
                    ts_local = ts.tz_convert(session_tz).strftime('%H:%M')
                    tracer({
                        'event': 'final_filter_check',
                        'ts': ts.isoformat(),
                        'ts_local': ts_local,
                        'in_session': in_session,
                        'side': sig.side
                    })
                
                if in_session:
                    filtered_signals.append(sig)
            
            if tracer:
                tracer({
                    'event': 'final_filter_result',
                    'signals_after': len(filtered_signals),
                    'filtered_out': len(signals) - len(filtered_signals)
                })
            
            return filtered_signals
        
        return signals
