#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 14 17:39:54 2025

@author: mirko
"""

"""Unit tests for Inside Bar strategy."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from strategies.inside_bar.strategy import InsideBarStrategy
from strategies.base import Signal


class TestInsideBarStrategy:
    """Test suite for Inside Bar strategy."""

    def setup_method(self):
        """Set up test fixtures."""
        self.strategy = InsideBarStrategy()

    def test_strategy_properties(self):
        """Test basic strategy properties."""
        from strategies.inside_bar.core import STRATEGY_VERSION as IB_VERSION

        assert self.strategy.name == "inside_bar"
        assert "Inside Bar breakout strategy" in self.strategy.description
        assert self.strategy.version == IB_VERSION

    def test_config_schema(self):
        """Test configuration schema."""
        schema = self.strategy.config_schema

        assert "properties" in schema
        assert "atr_period" in schema["properties"]
        assert "risk_reward_ratio" in schema["properties"]
        assert "inside_bar_mode" in schema["properties"]

        # Check required fields
        assert "required" in schema
        assert "atr_period" in schema["required"]
        assert "risk_reward_ratio" in schema["required"]

    def test_required_data_columns(self):
        """Test required data columns."""
        required = self.strategy.get_required_data_columns()
        expected = ["timestamp", "open", "high", "low", "close", "volume"]
        assert required == expected

    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        config = {
            "atr_period": 14,
            "risk_reward_ratio": 2.0,
            "inside_bar_mode": "inclusive",
        }
        assert self.strategy.validate_config(config) is True

    def test_validate_config_missing_required(self):
        """Test configuration validation with missing required fields."""
        config = {"inside_bar_mode": "inclusive"}
        assert self.strategy.validate_config(config) is False

    def create_sample_data(self, bars: int = 20) -> pd.DataFrame:
        """Create sample OHLCV data for testing."""
        base_time = datetime.now()
        data = []

        for i in range(bars):
            timestamp = base_time + timedelta(hours=i)
            # Create realistic OHLCV data
            base_price = 100 + i * 0.5  # Trending upward

            if i == 5:  # Create a mother bar at index 5
                open_price = base_price
                high = base_price + 2.0
                low = base_price - 1.0
                close = base_price + 1.0
            elif i == 6:  # Create an inside bar at index 6
                open_price = base_price
                high = base_price + 0.5  # Within mother bar range
                low = base_price - 0.5  # Within mother bar range
                close = base_price + 0.2
            elif i == 7:  # Create a breakout bar at index 7
                open_price = base_price
                high = base_price + 2.5  # Breaks above mother bar
                low = base_price - 0.2
                close = base_price + 2.2  # Closes above mother bar
            else:
                open_price = base_price
                high = base_price + 0.8
                low = base_price - 0.8
                close = base_price + np.random.uniform(-0.5, 0.5)

            data.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": 1000 + np.random.randint(0, 500),
                }
            )

        return pd.DataFrame(data)

    def test_preprocess_data(self):
        """Test data preprocessing."""
        data = self.create_sample_data()
        processed = self.strategy.preprocess_data(data)

        assert len(processed) == len(data)
        assert "timestamp" in processed.columns

        # Check if timestamp is properly converted
        assert pd.api.types.is_datetime64_any_dtype(processed["timestamp"])

    def test_generate_signals_basic(self):
        """Test basic signal generation."""
        data = self.create_sample_data(10)
        config = {
            "atr_period": 5,
            "risk_reward_ratio": 2.0,
            "inside_bar_mode": "inclusive",
            "breakout_confirmation": True,
        }

        signals = self.strategy.generate_signals(data, "TEST", config)

        # Should be a list of Signal objects
        assert isinstance(signals, list)
        for signal in signals:
            assert isinstance(signal, Signal)
            assert signal.symbol == "TEST"
            assert signal.strategy == "inside_bar"
            assert signal.signal_type in ["LONG", "SHORT"]

    def test_inside_bar_detection(self):
        """Test inside bar pattern detection."""
        # Create specific data pattern
        data = pd.DataFrame(
            [
                {
                    "timestamp": "2024-01-01T10:00:00",
                    "open": 100,
                    "high": 105,
                    "low": 95,
                    "close": 102,
                    "volume": 1000,
                },  # Mother bar
                {
                    "timestamp": "2024-01-01T11:00:00",
                    "open": 101,
                    "high": 103,
                    "low": 98,
                    "close": 99,
                    "volume": 1000,
                },  # Inside bar
                {
                    "timestamp": "2024-01-01T12:00:00",
                    "open": 99,
                    "high": 106,
                    "low": 97,
                    "close": 106,
                    "volume": 1000,
                },  # Breakout
            ]
        )

        config = {
            "atr_period": 2,
            "risk_reward_ratio": 2.0,
            "inside_bar_mode": "inclusive",
            "breakout_confirmation": True,
        }

        signals = self.strategy.generate_signals(data, "TEST", config)

        # Should generate a LONG signal on breakout
        assert len(signals) >= 1
        long_signals = [s for s in signals if s.signal_type == "LONG"]
        assert len(long_signals) >= 1

        signal = long_signals[0]
        assert signal.entry_price == 105  # Mother bar high
        assert signal.stop_loss == 95  # Mother bar low
        assert signal.take_profit > signal.entry_price

    def test_risk_reward_calculation(self):
        """Test risk-reward ratio calculations."""
        # Create data with known inside bar pattern
        data = pd.DataFrame(
            [
                {
                    "timestamp": "2024-01-01T10:00:00",
                    "open": 100,
                    "high": 110,
                    "low": 90,
                    "close": 105,
                    "volume": 1000,
                },  # Mother bar (range = 20)
                {
                    "timestamp": "2024-01-01T11:00:00",
                    "open": 102,
                    "high": 108,
                    "low": 95,
                    "close": 100,
                    "volume": 1000,
                },  # Inside bar
                {
                    "timestamp": "2024-01-01T12:00:00",
                    "open": 100,
                    "high": 115,
                    "low": 98,
                    "close": 112,
                    "volume": 1000,
                },  # Breakout
            ]
        )

        config = {
            "atr_period": 2,
            "risk_reward_ratio": 3.0,  # 3:1 RR
            "inside_bar_mode": "inclusive",
            "breakout_confirmation": True,
        }

        signals = self.strategy.generate_signals(data, "TEST", config)

        assert len(signals) >= 1
        signal = signals[0]

        risk = signal.entry_price - signal.stop_loss
        reward = signal.take_profit - signal.entry_price
        actual_rr = reward / risk

        assert abs(actual_rr - 3.0) < 0.01  # Should be close to 3:1

    def test_session_filter(self):
        """Test session time filtering."""
        # Create data with timestamps in different hours
        data = []
        base_time = datetime.strptime("2024-01-01T00:00:00", "%Y-%m-%dT%H:%M:%S")

        for i in range(24):  # 24 hours of data
            timestamp = base_time + timedelta(hours=i)
            data.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "open": 100 + i * 0.1,
                    "high": 102 + i * 0.1,
                    "low": 98 + i * 0.1,
                    "close": 101 + i * 0.1,
                    "volume": 1000,
                }
            )

        df = pd.DataFrame(data)

        # Create inside bar pattern at hour 8 and 16
        df.loc[7, ["high", "low"]] = [110, 90]  # Mother bar at hour 7
        df.loc[8, ["high", "low"]] = [105, 95]  # Inside bar at hour 8
        df.loc[9, "high"] = 115  # Breakout at hour 9

        config = {
            "atr_period": 2,
            "risk_reward_ratio": 2.0,
            "inside_bar_mode": "inclusive",
            "breakout_confirmation": True,
        }

        signals = self.strategy.generate_signals(df, "TEST", config)

        # Should only generate signals during session hours
        for signal in signals:
            signal_time = pd.to_datetime(signal.timestamp)
            hour = signal_time.hour
            assert 8 <= hour <= 16

    def test_sequence_mode(self):
        """Test sequence mode for multiple inside bars."""
        # Create data with sequence of inside bars
        data = pd.DataFrame(
            [
                {
                    "timestamp": "2024-01-01T10:00:00",
                    "open": 100,
                    "high": 110,
                    "low": 90,
                    "close": 105,
                    "volume": 1000,
                },  # Mother bar
                {
                    "timestamp": "2024-01-01T11:00:00",
                    "open": 102,
                    "high": 108,
                    "low": 95,
                    "close": 100,
                    "volume": 1000,
                },  # Inside bar 1
                {
                    "timestamp": "2024-01-01T12:00:00",
                    "open": 100,
                    "high": 107,
                    "low": 96,
                    "close": 103,
                    "volume": 1000,
                },  # Inside bar 2
                {
                    "timestamp": "2024-01-01T13:00:00",
                    "open": 103,
                    "high": 115,
                    "low": 100,
                    "close": 112,
                    "volume": 1000,
                },  # Breakout
            ]
        )

        config = {
            "atr_period": 3,
            "risk_reward_ratio": 2.0,
            "inside_bar_mode": "inclusive",
            "breakout_confirmation": True,
        }

        signals = self.strategy.generate_signals(data, "TEST", config)

        # Unified core currently uses the most recent mother/inside pattern.
        # We assert on the concrete prices produced by the core for this
        # synthetic sequence rather than the legacy "sequence" behaviour.
        assert len(signals) >= 1
        signal = signals[0]
        assert signal.entry_price == 108.0
        assert signal.stop_loss == 95.0

    def test_insufficient_data(self):
        """Test behavior with insufficient data."""
        # Single row of data
        data = pd.DataFrame(
            [
                {
                    "timestamp": "2024-01-01T10:00:00",
                    "open": 100,
                    "high": 105,
                    "low": 95,
                    "close": 102,
                    "volume": 1000,
                }
            ]
        )

        config = {"atr_period": 14, "risk_reward_ratio": 2.0}

        signals = self.strategy.generate_signals(data, "TEST", config)
        assert signals == []  # Should return empty list

    def test_invalid_data_validation(self):
        """Test data validation with missing columns."""
        # Data missing required columns
        data = pd.DataFrame(
            [
                {
                    "timestamp": "2024-01-01T10:00:00",
                    "open": 100,
                    "close": 102,
                }  # Missing high, low, volume
            ]
        )

        config = {"atr_period": 14, "risk_reward_ratio": 2.0}

        with pytest.raises(ValueError, match="Missing required columns"):
            self.strategy.generate_signals(data, "TEST", config)

    def test_signal_metadata(self):
        """Test signal metadata content."""
        data = self.create_sample_data(10)
        config = {
            "atr_period": 5,
            "risk_reward_ratio": 2.0,
            "inside_bar_mode": "inclusive",
        }

        signals = self.strategy.generate_signals(data, "TEST", config)

        for signal in signals:
            assert "pattern" in signal.metadata
            assert signal.metadata["pattern"] == "inside_bar_breakout"
            # Unified core publishes mother_high/mother_low keys
            assert "mother_high" in signal.metadata
            assert "mother_low" in signal.metadata
            assert "atr" in signal.metadata

    def test_no_breakout_confirmation(self):
        """Test signals without breakout confirmation."""
        # Create data where high/low touches mother bar but close doesn't
        data = pd.DataFrame(
            [
                {
                    "timestamp": "2024-01-01T10:00:00",
                    "open": 100,
                    "high": 110,
                    "low": 90,
                    "close": 105,
                    "volume": 1000,
                },  # Mother bar
                {
                    "timestamp": "2024-01-01T11:00:00",
                    "open": 102,
                    "high": 108,
                    "low": 95,
                    "close": 100,
                    "volume": 1000,
                },  # Inside bar
                {
                    "timestamp": "2024-01-01T12:00:00",
                    "open": 100,
                    "high": 112,
                    "low": 98,
                    "close": 101,
                    "volume": 1000,
                },  # High breaks but close doesn't
            ]
        )

        # Test with confirmation disabled
        config_no_confirm = {
            "atr_period": 2,
            "risk_reward_ratio": 2.0,
            "breakout_confirmation": False,
        }

        signals_no_confirm = self.strategy.generate_signals(
            data, "TEST", config_no_confirm
        )

        # Test with confirmation enabled
        config_confirm = {
            "atr_period": 2,
            "risk_reward_ratio": 2.0,
            "breakout_confirmation": True,
        }

        signals_confirm = self.strategy.generate_signals(data, "TEST", config_confirm)

        # Without confirmation should generate signal, with confirmation should not
        assert len(signals_no_confirm) > len(signals_confirm)
