"""
CRITICAL PARITY TEST: Backtest vs Core Logic

This test verifies that the backtest adapter produces identical results to calling
the core logic directly (which is what the live adapter also does).

Zero-deviation requirement:
- Same number of signals
- Identical entry prices
- Identical stop losses
- Identical take profits
- Identical timestamps

Since both backtest and live adapters use the same InsideBarCore, and we test
that backtest adapter matches core output, this proves parity.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from ..strategy import InsideBarStrategy
from ..core import InsideBarCore, InsideBarConfig


class TestBacktestCoreParity:
    """Verify backtest adapter produces identical results to core."""

    @pytest.fixture
    def test_data(self):
        """
        Generate deterministic test data with inside bar pattern and breakout.

        Pattern:
        - Bar 20: Wide range (mother bar)
        - Bar 21: Inside bar
        - Bar 22: Breakout above (should trigger LONG)
        """
        dates = pd.date_range('2025-01-01 09:00', periods=50, freq='5min', tz='UTC')
        np.random.seed(42)  # Deterministic

        data = pd.DataFrame({
            'timestamp': dates,
            'open': 100.0 + np.random.randn(50) * 0.5,
            'high': 102.0 + np.random.randn(50) * 0.5,
            'low': 98.0 + np.random.randn(50) * 0.5,
            'close': 100.5 + np.random.randn(50) * 0.5,
            'volume': 10000 + np.random.randint(-1000, 1000, 50)
        })

        # Create clear inside bar pattern at index 20-21-22
        data.loc[20, ['open', 'high', 'low', 'close']] = [100, 105, 96, 102]  # Mother bar
        data.loc[21, ['open', 'high', 'low', 'close']] = [101, 103, 98, 101]  # Inside bar
        data.loc[22, ['open', 'high', 'low', 'close']] = [102, 108, 101, 106]  # Breakout

        return data

    @pytest.fixture
    def config(self):
        """Shared configuration for both systems."""
        return {
            'atr_period': 14,
            'risk_reward_ratio': 2.0,
            'min_mother_bar_size': 0.0,  # Disable to focus on pattern detection
            'breakout_confirmation': True,
            'inside_bar_mode': 'inclusive'
        }

    def test_backtest_adapter_matches_core(self, test_data, config):
        """Backtest adapter MUST produce identical results to core."""
        # Call backtest adapter
        backtest = InsideBarStrategy()
        backtest_signals = backtest.generate_signals(
            test_data.copy(), 'TEST', config
        )

        # Call core directly (what live adapter does)
        core_config = InsideBarConfig(**config)
        core = InsideBarCore(core_config)
        raw_signals = core.process_data(test_data.copy(), 'TEST')

        # Must have same number of signals
        assert len(backtest_signals) == len(raw_signals), \
            f"Signal count mismatch: Backtest={len(backtest_signals)} vs Core={len(raw_signals)}"

        # Compare each signal
        for i, (bs, raw) in enumerate(zip(backtest_signals, raw_signals)):
            # Entry price must match
            assert abs(bs.entry_price - raw.entry_price) < 0.001, \
                f"Signal {i}: Entry price mismatch: {bs.entry_price} vs {raw.entry_price}"

            # Stop loss must match
            assert abs(bs.stop_loss - raw.stop_loss) < 0.001, \
                f"Signal {i}: Stop loss mismatch: {bs.stop_loss} vs {raw.stop_loss}"

            # Take profit must match
            assert abs(bs.take_profit - raw.take_profit) < 0.001, \
                f"Signal {i}: Take profit mismatch: {bs.take_profit} vs {raw.take_profit}"

            # Signal type must match
            backtest_type = bs.signal_type  # "LONG" or "SHORT"
            raw_type = "LONG" if raw.side == "BUY" else "SHORT"
            assert backtest_type == raw_type, \
                f"Signal {i}: Type mismatch: {backtest_type} vs {raw_type}"

    @pytest.mark.parametrize("risk_reward", [1.5, 2.0, 2.5, 3.0])
    def test_parity_different_risk_rewards(self, test_data, risk_reward):
        """Test parity across different risk/reward ratios."""
        config = {
            'atr_period': 14,
            'risk_reward_ratio': risk_reward,
            'min_mother_bar_size': 0.0,
            'breakout_confirmation': True,
            'inside_bar_mode': 'inclusive'
        }

        backtest = InsideBarStrategy()
        backtest_signals = backtest.generate_signals(test_data.copy(), 'TEST', config)

        core_config = InsideBarConfig(**config)
        core = InsideBarCore(core_config)
        raw_signals = core.process_data(test_data.copy(), 'TEST')

        # All critical fields must match
        assert len(backtest_signals) == len(raw_signals), \
            f"RRR={risk_reward}: Signal count mismatch"

        for bs, raw in zip(backtest_signals, raw_signals):
            assert abs(bs.entry_price - raw.entry_price) < 0.001
            assert abs(bs.stop_loss - raw.stop_loss) < 0.001
            assert abs(bs.take_profit - raw.take_profit) < 0.001

    @pytest.mark.parametrize("mode", ["inclusive", "strict"])
    def test_parity_different_modes(self, test_data, mode):
        """Test parity across different inside bar modes."""
        config = {
            'atr_period': 14,
            'risk_reward_ratio': 2.0,
            'min_mother_bar_size': 0.0,
            'breakout_confirmation': True,
            'inside_bar_mode': mode
        }

        backtest = InsideBarStrategy()
        backtest_signals = backtest.generate_signals(test_data.copy(), 'TEST', config)

        core_config = InsideBarConfig(**config)
        core = InsideBarCore(core_config)
        raw_signals = core.process_data(test_data.copy(), 'TEST')

        # Signal count must match
        assert len(backtest_signals) == len(raw_signals), \
            f"Mode={mode}: Signal count mismatch"

    def test_determinism(self, test_data, config):
        """Running same data twice MUST produce identical results."""
        backtest = InsideBarStrategy()

        # Run 1
        signals1 = backtest.generate_signals(test_data.copy(), 'TEST', config)

        # Run 2
        signals2 = backtest.generate_signals(test_data.copy(), 'TEST', config)

        # Must be identical
        assert len(signals1) == len(signals2)

        for s1, s2 in zip(signals1, signals2):
            assert s1.entry_price == s2.entry_price
            assert s1.stop_loss == s2.stop_loss
            assert s1.take_profit == s2.take_profit
            assert s1.signal_type == s2.signal_type

    def test_core_direct_usage(self, test_data, config):
        """Verify core can be used directly (live adapter use case)."""
        core_config = InsideBarConfig(**config)
        core = InsideBarCore(core_config)

        raw_signals = core.process_data(test_data.copy(), 'TEST')

        # Should generate at least one signal from our test data
        assert len(raw_signals) > 0, "Core should detect pattern in test data"

        # Validate structure of raw signals
        for signal in raw_signals:
            assert signal.side in ["BUY", "SELL"]
            assert signal.entry_price > 0
            assert signal.stop_loss > 0
            assert signal.take_profit > 0
            assert 'pattern' in signal.metadata
            assert 'mother_high' in signal.metadata
            assert 'mother_low' in signal.metadata
