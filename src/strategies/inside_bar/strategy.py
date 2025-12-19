"""
Backtest adapter for InsideBar strategy.

This adapter wraps the unified core logic and converts RawSignals
to Backtest Signal objects.

IMPORTANT: This is just an I/O adapter. ALL strategy logic is in core.py
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional, Callable
import pandas as pd

from ..base import BaseStrategy, Signal
from .core import InsideBarCore, InsideBarConfig, RawSignal
from .core import STRATEGY_VERSION as _IB_CORE_VERSION


class InsideBarStrategy(BaseStrategy):
    """
    InsideBar strategy for backtesting.
    
    This is a thin adapter that:
    1. Accepts backtest-format inputs
    2. Delegates to InsideBarCore for logic
    3. Converts RawSignals to Backtest Signals
    
    Zero custom logic - everything delegates to core.py
    """
    
    @property
    def name(self) -> str:
        """Return strategy name."""
        return "inside_bar"
    
    @property
    def version(self) -> str:
        """Return strategy version from unified core metadata."""
        return _IB_CORE_VERSION
    
    @property
    def description(self) -> str:
        """Return strategy description."""
        return (
            "Inside Bar breakout strategy with ATR-based risk management. "
            "Detects inside bar patterns and generates signals on breakouts "
            "with configurable risk-reward ratios. "
            "Version 2.0 - Unified core logic."
        )
    
    @property
    def config_schema(self) -> Dict[str, Any]:
        """Return configuration schema."""
        return {
            "type": "object",
            "properties": {
                "atr_period": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 14,
                    "description": "Period for ATR calculation",
                },
                "risk_reward_ratio": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 10.0,
                    "default": 2.0,
                    "description": "Risk-reward ratio (take_profit / stop_loss)",
                },
                "inside_bar_mode": {
                    "type": "string",
                    "enum": ["inclusive", "strict"],
                    "default": "inclusive",
                    "description": "Mode for inside bar detection",
                },
                "min_mother_bar_size": {
                    "type": "number",
                    "minimum": 0.0,
                    "default": 0.5,
                    "description": "Minimum size of mother bar as multiple of ATR",
                },
                "breakout_confirmation": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "Require breakout confirmation (close beyond mother bar)"
                    ),
                },
            },
            "required": ["atr_period", "risk_reward_ratio"],
        }
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        symbol: str,
        config: Dict[str, Any],
        tracer: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Signal]:
        """
        Generate Inside Bar signals for backtesting.
        
        This method:
        1. Validates input data
        2. Creates InsideBarConfig from dict
        3. Delegates to InsideBarCore
        4. Converts RawSignals to Backtest Signals
        
        Args:
            data: OHLCV DataFrame with columns: timestamp, open, high, low, close, volume
            symbol: Trading symbol
            config: Strategy configuration dict
            
        Returns:
            List of Signal objects (backtest format)
        """
        # Validate input data
        self.validate_data(data)
        
        # Preprocess (ensure timestamp is datetime)
        df = self.preprocess_data(data.copy())
        
        # Create InsideBarConfig from dict
        # Extract only params supported by core
        core_params = {
            # Core
            'atr_period': config.get('atr_period', 14),
            'risk_reward_ratio': config.get('risk_reward_ratio', 2.0),
            'min_mother_bar_size': config.get('min_mother_bar_size', 0.5),
            'breakout_confirmation': config.get('breakout_confirmation', True),
            'inside_bar_mode': config.get('inside_bar_mode', 'inclusive'),

            # Session & TZ
            'session_timezone': config.get('session_timezone', 'Europe/Berlin'),
            'session_windows': config.get('session_filter')
                or config.get('session_windows', ['15:00-16:00', '16:00-17:00']),
            'max_trades_per_session': config.get('max_trades_per_session', 1),

            # Order validity
            'order_validity_policy': config.get('order_validity_policy', 'session_end'),
            'order_validity_minutes': config.get('order_validity_minutes', 60),
            'valid_from_policy': config.get('valid_from_policy', 'signal_ts'),

            # Entry/SL sizing
            'entry_level_mode': config.get('entry_level_mode', 'mother_bar'),
            'stop_distance_cap_ticks': config.get('stop_distance_cap_ticks', 40),
            'tick_size': config.get('tick_size', 0.01),

            # Trailing (pass-through, defaults already validated)
            'trailing_enabled': config.get('trailing_enabled', False),
            'trailing_trigger_tp_pct': config.get('trailing_trigger_tp_pct', 0.70),
            'trailing_risk_remaining_pct': config.get('trailing_risk_remaining_pct', 0.50),
            'trailing_apply_mode': config.get('trailing_apply_mode', 'next_bar'),
        }
        
        strategy_config = InsideBarConfig(**core_params)
        
        # Delegate to core
        core = InsideBarCore(strategy_config)
        raw_signals = core.process_data(df, symbol, tracer=tracer)
        
        # Convert RawSignals to Backtest Signals
        signals = []
        for raw in raw_signals:
            # Convert timestamp to ISO string
            timestamp_str = pd.to_datetime(raw.timestamp).isoformat()
            
            # Map BUY/SELL to LONG/SHORT
            signal_type = "LONG" if raw.side == "BUY" else "SHORT"
            
            # Create backtest Signal
            # Remove 'symbol' from metadata to avoid conflict
            metadata = {k: v for k, v in raw.metadata.items() if k != 'symbol'}
            
            signal = self.create_signal(
                timestamp=timestamp_str,
                symbol=symbol,
                signal_type=signal_type,
                confidence=0.8,  # Fixed confidence for inside bar
                entry_price=raw.entry_price,
                stop_loss=raw.stop_loss,
                take_profit=raw.take_profit,
                **metadata  # Pass through filtered metadata
            )
            signals.append(signal)
        
        return signals
    
    def get_required_data_columns(self) -> List[str]:
        """Return required data columns."""
        return ["timestamp", "open", "high", "low", "close", "volume"]
    
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Preprocess data for inside bar detection."""
        df = super().preprocess_data(data)
        
        # Ensure data is sorted by timestamp
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp").reset_index(drop=True)
        
        # Remove any duplicate timestamps
        if "timestamp" in df.columns:
            df = df.drop_duplicates(subset=["timestamp"], keep="last")
        
        return df
