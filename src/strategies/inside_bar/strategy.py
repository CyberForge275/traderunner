#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 14 17:59:19 2025

@author: mirko
"""

"""Inside Bar Pattern Trading Strategy.

This strategy detects inside bar patterns and generates trading signals based on
breakouts from the pattern. An inside bar is a candlestick that is completely
contained within the previous bar's high and low range.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any

from ..base import BaseStrategy, Signal


class InsideBarStrategy(BaseStrategy):
    """Inside Bar pattern recognition strategy.

    This strategy identifies inside bar patterns and generates signals when:
    1. An inside bar is detected (current bar is within previous bar's range)
    2. Price breaks out above/below the mother bar (the bar containing the inside bar)
    3. Risk management using ATR for stop losses and take profits

    Features:
    - Configurable ATR period for volatility-based stops
    - Risk-reward ratio management
    - Session filtering (optional)
    - Multiple inside bar modes (single, sequence)
    """

    @property
    def name(self) -> str:
        """Return strategy name."""
        return "inside_bar_v1"

    @property
    def description(self) -> str:
        """Return strategy description."""
        return (
            "Inside Bar breakout strategy with ATR-based risk management. "
            "Detects inside bar patterns and generates signals on breakouts "
            "with configurable risk-reward ratios."
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
                    "enum": ["single", "sequence"],
                    "default": "single",
                    "description": "Mode for inside bar detection",
                },
                "min_mother_bar_size": {
                    "type": "number",
                    "minimum": 0.0,
                    "default": 0.0,
                    "description": "Minimum size of mother bar as multiple of ATR",
                },
                "breakout_confirmation": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "Require breakout confirmation (close beyond mother bar)"
                    ),
                },
                "session_filter": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean", "default": False},
                        "start_hour": {"type": "integer", "minimum": 0, "maximum": 23},
                        "end_hour": {"type": "integer", "minimum": 0, "maximum": 23},
                    },
                    "description": "Optional session time filtering",
                },
            },
            "required": ["atr_period", "risk_reward_ratio"],
        }

    def generate_signals(
        self, data: pd.DataFrame, symbol: str, config: Dict[str, Any]
    ) -> List[Signal]:
        """Generate Inside Bar signals.

        Args:
            data: OHLCV DataFrame with columns: timestamp, open, high, low,
                close, volume
            symbol: Trading symbol
            config: Strategy configuration

        Returns:
            List of Signal objects
        """
        # Validate input data
        self.validate_data(data)

        # Preprocess data
        df = self.preprocess_data(data.copy())

        if len(df) < 2:
            return []

        # Extract configuration
        atr_period = config.get("atr_period", 14)
        rrr = config.get("risk_reward_ratio", 2.0)
        inside_bar_mode = config.get("inside_bar_mode", "single")
        min_mother_size = config.get("min_mother_bar_size", 0.0)
        breakout_confirm = config.get("breakout_confirmation", True)
        session_filter = config.get("session_filter", {"enabled": False})

        # Calculate technical indicators
        df = self._calculate_indicators(df, atr_period)

        # Detect inside bars
        df = self._detect_inside_bars(df, inside_bar_mode, min_mother_size)

        # Apply session filter if enabled
        if session_filter.get("enabled", False):
            df = self._apply_session_filter(df, session_filter)

        # Generate breakout signals
        signals = self._generate_breakout_signals(df, symbol, rrr, breakout_confirm)

        return signals

    def _calculate_indicators(self, df: pd.DataFrame, atr_period: int) -> pd.DataFrame:
        """Calculate technical indicators including ATR."""
        # Calculate True Range
        df["prev_close"] = df["close"].shift(1)
        df["tr1"] = df["high"] - df["low"]
        df["tr2"] = abs(df["high"] - df["prev_close"])
        df["tr3"] = abs(df["low"] - df["prev_close"])
        df["true_range"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

        # Calculate ATR (Average True Range)
        df["atr"] = df["true_range"].rolling(window=atr_period).mean()

        # Calculate previous bar's range
        df["prev_high"] = df["high"].shift(1)
        df["prev_low"] = df["low"].shift(1)
        df["prev_range"] = df["prev_high"] - df["prev_low"]

        return df

    def _detect_inside_bars(
        self, df: pd.DataFrame, mode: str, min_mother_size: float
    ) -> pd.DataFrame:
        """Detect inside bar patterns."""
        df["is_inside_bar"] = False
        df["mother_bar_high"] = np.nan
        df["mother_bar_low"] = np.nan
        df["mother_bar_index"] = -1

        for i in range(1, len(df)):
            prev_high = df.iloc[i - 1]["high"]
            prev_low = df.iloc[i - 1]["low"]
            curr_high = df.iloc[i]["high"]
            curr_low = df.iloc[i]["low"]
            atr = df.iloc[i]["atr"]

            # Check if current bar is inside previous bar
            is_inside = (curr_high <= prev_high) and (curr_low >= prev_low)

            # Check minimum mother bar size if specified
            if is_inside and min_mother_size > 0 and not pd.isna(atr):
                mother_range = prev_high - prev_low
                if mother_range < (min_mother_size * atr):
                    is_inside = False

            if is_inside:
                df.iloc[i, df.columns.get_loc("is_inside_bar")] = True
                df.iloc[i, df.columns.get_loc("mother_bar_high")] = prev_high
                df.iloc[i, df.columns.get_loc("mother_bar_low")] = prev_low
                df.iloc[i, df.columns.get_loc("mother_bar_index")] = i - 1

                # For sequence mode, check if previous bar was also an inside bar
                if mode == "sequence" and i >= 2:
                    if df.iloc[i - 1]["is_inside_bar"]:
                        # Use the original mother bar, not the previous inside bar
                        orig_mother_idx = df.iloc[i - 1]["mother_bar_index"]
                        if orig_mother_idx >= 0:
                            df.iloc[i, df.columns.get_loc("mother_bar_high")] = df.iloc[
                                int(orig_mother_idx)
                            ]["high"]
                            df.iloc[i, df.columns.get_loc("mother_bar_low")] = df.iloc[
                                int(orig_mother_idx)
                            ]["low"]
                            df.iloc[i, df.columns.get_loc("mother_bar_index")] = (
                                orig_mother_idx
                            )

        return df

    def _apply_session_filter(
        self, df: pd.DataFrame, session_config: Dict
    ) -> pd.DataFrame:
        """Apply session time filter."""
        if not session_config.get("enabled", False):
            return df

        start_hour = session_config.get("start_hour", 0)
        end_hour = session_config.get("end_hour", 23)

        # Extract hour from timestamp
        if "timestamp" in df.columns:
            df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour

            # Create session mask
            if start_hour <= end_hour:
                session_mask = (df["hour"] >= start_hour) & (df["hour"] <= end_hour)
            else:  # Overnight session
                session_mask = (df["hour"] >= start_hour) | (df["hour"] <= end_hour)

            df["in_session"] = session_mask
        else:
            df["in_session"] = True

        return df

    def _generate_breakout_signals(
        self, df: pd.DataFrame, symbol: str, rrr: float, confirm: bool
    ) -> List[Signal]:
        """Generate breakout signals from inside bar patterns."""
        signals = []

        # Check each bar for potential breakouts from recent inside bar patterns
        for i in range(len(df)):
            row = df.iloc[i]

            # Skip if session filter enabled and not in session
            if "in_session" in df.columns and not row["in_session"]:
                continue

            # Skip if ATR not available
            if pd.isna(row["atr"]):
                continue

            # Look for inside bar patterns in previous bars (within last 5 bars)
            inside_bar_found = False
            mother_high = None
            mother_low = None
            inside_bar_atr = None

            # Check current and previous bars for inside bar patterns
            for j in range(max(0, i - 4), i + 1):  # Check last 5 bars including current
                check_row = df.iloc[j]
                if check_row["is_inside_bar"] and not pd.isna(check_row["mother_bar_high"]):
                    inside_bar_found = True
                    mother_high = check_row["mother_bar_high"]
                    mother_low = check_row["mother_bar_low"]
                    inside_bar_atr = check_row["atr"]
                    break  # Use the most recent inside bar

            if not inside_bar_found:
                continue

            current_close = row["close"]
            atr = inside_bar_atr if not pd.isna(inside_bar_atr) else row["atr"]

            # Check for breakout
            long_breakout = False
            short_breakout = False

            if confirm:
                # Require close beyond mother bar range
                if current_close > mother_high:
                    long_breakout = True
                elif current_close < mother_low:
                    short_breakout = True
            else:
                # Just require high/low beyond mother bar range
                if row["high"] > mother_high:
                    long_breakout = True
                elif row["low"] < mother_low:
                    short_breakout = True

            # Generate signals
            if long_breakout:
                entry_price = mother_high
                stop_loss = mother_low
                risk = entry_price - stop_loss
                take_profit = entry_price + (risk * rrr)

                signal = self.create_signal(
                    timestamp=row["timestamp"],
                    symbol=symbol,
                    signal_type="LONG",
                    confidence=0.8,  # Base confidence for inside bar breakouts
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    pattern="inside_bar_breakout",
                    mother_bar_high=mother_high,
                    mother_bar_low=mother_low,
                    atr=atr,
                    risk_amount=risk,
                    reward_amount=risk * rrr,
                )
                signals.append(signal)

            elif short_breakout:
                entry_price = mother_low
                stop_loss = mother_high
                risk = stop_loss - entry_price
                take_profit = entry_price - (risk * rrr)

                signal = self.create_signal(
                    timestamp=row["timestamp"],
                    symbol=symbol,
                    signal_type="SHORT",
                    confidence=0.8,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    pattern="inside_bar_breakout",
                    mother_bar_high=mother_high,
                    mother_bar_low=mother_low,
                    atr=atr,
                    risk_amount=risk,
                    reward_amount=risk * rrr,
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
