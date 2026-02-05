"""
Unit tests for InsideBar Core Logic.

Critical: These tests ensure core logic is deterministic and correct.
All tests MUST pass before deploying.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from ..core import InsideBarCore, InsideBarConfig
from ..models import RawSignal


def _cfg(**overrides):
    base = {"inside_bar_definition_mode": "mb_body_oc__ib_hl"}
    base.update(overrides)
    return InsideBarConfig(**base)


class TestInsideBarConfig:
    """Test configuration validation."""

    def test_missing_definition_mode(self):
        with pytest.raises(TypeError):
            InsideBarConfig()  # type: ignore[call-arg]

    def test_default_config(self):
        """Default config should be valid."""
        config = _cfg()
        assert config.atr_period == 14
        assert config.risk_reward_ratio == 2.0
        assert config.inside_bar_mode == "inclusive"

    def test_invalid_atr_period(self):
        """Negative ATR period should raise error."""
        with pytest.raises(AssertionError):
            _cfg(atr_period=-1)

    def test_invalid_risk_reward(self):
        """Zero risk/reward should raise error."""
        with pytest.raises(AssertionError):
            _cfg(risk_reward_ratio=0)

    def test_invalid_mode(self):
        """Invalid mode should raise error."""
        with pytest.raises(AssertionError):
            _cfg(inside_bar_mode="invalid")


class TestATRCalculation:
    """Test ATR calculation accuracy."""

    @pytest.fixture
    def simple_data(self):
        """Create simple test data."""
        dates = pd.date_range('2025-01-01', periods=20, freq='5min')
        return pd.DataFrame({
            'timestamp': dates,
            'open': [100.0] * 20,
            'high': [101.0, 102.0, 103.0, 104.0, 105.0] * 4,
            'low': [99.0, 98.0, 97.0, 96.0, 95.0] * 4,
            'close': [100.5, 101.5, 102.5, 103.5, 104.5] * 4,
        })

    def test_atr_calculation(self, simple_data):
        """ATR should be calculated correctly."""
        config = _cfg(atr_period=5)
        core = InsideBarCore(config)

        result = core.calculate_atr(simple_data)

        # Check columns exist
        assert 'atr' in result.columns
        assert 'true_range' in result.columns
        assert 'prev_close' in result.columns

        # ATR should be NaN for first atr_period-1 rows
        assert pd.isna(result.iloc[0]['atr'])
        assert pd.isna(result.iloc[3]['atr'])  # index 3 (4th row) is still NaN

        # ATR should have value at index atr_period (5th row)
        assert pd.notna(result.iloc[4]['atr'])
        assert result.iloc[4]['atr'] > 0

    def test_atr_positive(self, simple_data):
        """ATR values should always be positive."""
        config = _cfg()
        core = InsideBarCore(config)

        result = core.calculate_atr(simple_data)

        # All non-NaN ATR values should be positive
        atr_values = result['atr'].dropna()
        assert (atr_values > 0).all()


class TestInsideBarDetection:
    """Test inside bar pattern detection."""

    @pytest.fixture
    def inside_bar_data(self):
        """Create data with clear inside bar pattern."""
        dates = pd.date_range('2025-01-01', periods=5, freq='5min')
        return pd.DataFrame({
            'timestamp': dates,
            # idx=1 is mother bar with body 100-102 (open=100, close=102)
            # idx=2 is inside bar: full high/low inside mother body
            'open': [100, 100, 101.0, 102, 103],
            'high': [102, 103, 101.5, 104, 105],
            'low': [99, 98, 100.5, 100, 101],
            'close': [101, 102, 101.2, 103, 104],
        })

    def test_detect_inside_bar_inclusive(self, inside_bar_data):
        """Should detect inside bar in inclusive mode."""
        config = _cfg(
            inside_bar_mode="inclusive",
            min_mother_bar_size=0  # Disable size filter
        )
        core = InsideBarCore(config)

        # Calculate ATR first
        df = core.calculate_atr(inside_bar_data)

        # Detect inside bars
        result = core.detect_inside_bars(df)

        # Check columns exist
        assert 'is_inside_bar' in result.columns
        assert 'mother_bar_high' in result.columns
        assert 'mother_bar_low' in result.columns

        # Index 2 should be inside bar (inside index 1)
        # high[2]=101.5 <= body_high[1]=102 ✓
        # low[2]=100.5 >= body_low[1]=100 ✓
        # close[2]=101.2 within body_low/high (100-102) ✓
        assert result.iloc[2]['is_inside_bar'] == True
        assert result.iloc[2]['mother_bar_high'] == 103.0
        assert result.iloc[2]['mother_bar_low'] == 98.0

    def test_mother_size_filter_disabled_when_zero(self, inside_bar_data):
        """min_mother_bar_size=0 should disable size filter even if ATR is NaN."""
        config = _cfg(
            inside_bar_mode="inclusive",
            min_mother_bar_size=0  # Disable size filter
        )
        core = InsideBarCore(config)

        df = core.calculate_atr(inside_bar_data)  # ATR will be NaN for early rows
        result = core.detect_inside_bars(df)

        # Inside bar should still be detected when filter is disabled
        assert result.iloc[2]['is_inside_bar'] == True

    def test_mother_size_filter_uses_mother_atr(self):
        """Mother size filter should use mother bar ATR (i-1), not inside bar ATR (i)."""
        dates = pd.date_range('2025-01-01', periods=4, freq='5min')
        data = pd.DataFrame({
            'timestamp': dates,
            # mother bar (idx=1): open=100 close=110 => body 100-110
            # inside bar (idx=2): full HL inside body
            'open': [100, 100, 102, 103],
            'high': [110, 110, 109, 111],
            'low': [90, 95, 100.5, 102],
            'close': [105, 110, 105, 106],
        })

        config = _cfg(
            inside_bar_mode="inclusive",
            min_mother_bar_size=1.0,
            atr_period=2
        )
        core = InsideBarCore(config)

        df = core.calculate_atr(data)
        # Force distinct ATR values at mother vs inside bars
        df.loc[1, 'atr'] = 5.0   # mother ATR
        df.loc[2, 'atr'] = 15.0  # inside ATR (should NOT be used)

        result = core.detect_inside_bars(df)

        # mother_range = 110 - 100 = 10; min_size = 1.0 * mother_ATR = 5 -> pass
        assert result.iloc[2]['is_inside_bar'] == True

    def test_mother_size_filter_rejects_when_atr_missing(self):
        """If min_mother_bar_size>0 and mother ATR is missing/<=0, reject."""
        dates = pd.date_range('2025-01-01', periods=4, freq='5min')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': [100, 101, 102, 103],
            'high': [110, 110, 109, 111],
            'low': [90, 100, 101, 102],
            'close': [105, 105, 105, 106],
        })

        config = _cfg(
            inside_bar_mode="inclusive",
            min_mother_bar_size=1.0,
            atr_period=2
        )
        core = InsideBarCore(config)

        df = core.calculate_atr(data)
        df.loc[1, 'atr'] = 0.0  # mother ATR missing/invalid

        result = core.detect_inside_bars(df)
        assert result.iloc[2]['is_inside_bar'] == False

    def test_detect_inside_bar_strict(self):
        """Should NOT detect if touching in strict mode."""
        dates = pd.date_range('2025-01-01', periods=3, freq='5min')
        data = pd.DataFrame({
            'timestamp': dates,
            # mother bar body: 100-102 (open=100, close=102)
            'open': [100, 100, 100.5],
            'high': [102, 103, 102],  # idx=2 touches body_high
            'low': [99, 98, 99],
            'close': [101, 102, 102],  # close touches body_high
        })

        config = _cfg(
            inside_bar_mode="strict",
            min_mother_bar_size=0
        )
        core = InsideBarCore(config)

        df = core.calculate_atr(data)
        result = core.detect_inside_bars(df)

        # Should NOT be inside bar in strict mode (touching is not allowed)
        assert result.iloc[2]['is_inside_bar'] == False

    def test_detect_inside_bar_bearish_mother_body(self):
        """Inside bar detection should respect bearish mother body (open > close)."""
        dates = pd.date_range('2025-01-02', periods=3, freq='5min')
        data = pd.DataFrame({
            'timestamp': dates,
            # mother bar body: 101 (close) to 103 (open)
            'open': [102, 103, 102.5],
            'high': [104, 105, 102.8],
            'low': [100, 100, 101.2],
            'close': [101, 101, 101.5],
        })
        config = _cfg(inside_bar_mode="inclusive", min_mother_bar_size=0)
        core = InsideBarCore(config)
        df = core.calculate_atr(data)
        result = core.detect_inside_bars(df)
        assert result.iloc[2]['is_inside_bar'] == True

    def test_inside_bar_high_outside_body_rejected(self):
        """High above mother body_high should reject inside bar."""
        dates = pd.date_range('2025-01-03', periods=3, freq='5min')
        data = pd.DataFrame({
            'timestamp': dates,
            # mother body: 100-102
            'open': [100, 100, 101.0],
            'high': [102, 103, 103.5],  # idx=2 high outside body
            'low': [99, 98, 97.0],
            'close': [101, 102, 101.0],
        })
        core = InsideBarCore(_cfg(inside_bar_mode="inclusive", min_mother_bar_size=0))
        df = core.calculate_atr(data)
        result = core.detect_inside_bars(df)
        assert result.iloc[2]['is_inside_bar'] == False

    def test_inside_bar_close_outside_body_rejected(self):
        """Close outside mother body should reject inside bar even if high is inside."""
        dates = pd.date_range('2025-01-04', periods=3, freq='5min')
        data = pd.DataFrame({
            'timestamp': dates,
            # mother body: 100-102
            'open': [100, 100, 101.0],
            'high': [102, 103, 101.5],
            'low': [99, 98, 97.0],
            'close': [101, 102, 102.5],  # close outside body_high
        })
        core = InsideBarCore(_cfg(inside_bar_mode="inclusive", min_mother_bar_size=0))
        df = core.calculate_atr(data)
        result = core.detect_inside_bars(df)
        assert result.iloc[2]['is_inside_bar'] == False


class TestSignalGeneration:
    """Test trading signal generation."""

    @pytest.fixture
    def breakout_data(self):
        """Create data with inside bar and breakout."""
        dates = pd.date_range('2025-01-01 14:00', periods=10, freq='5min', tz='UTC')
        return pd.DataFrame({
            'timestamp': dates,
            # Bar 0-1: Normal
            # Bar 2: Inside bar (inside bar 1)
            # Bar 3: Breakout above (BUY signal expected)
            # mother (idx=1) body: 100-103, inside (idx=2) high/close inside body
            'open':  [100, 100, 101.0, 104, 105, 106, 107, 108, 109, 110],
            'high':  [102, 103, 102.5, 106, 107, 108, 109, 110, 111, 112],
            'low':   [99,  98,  100.5, 103, 104, 105, 106, 107, 108, 109],
            'close': [101, 103, 101.5, 105, 106, 107, 108, 109, 110, 111],
        })

    def test_generate_long_signal(self, breakout_data):
        """Should generate LONG signal on upside breakout."""
        config = _cfg(
            breakout_confirmation=True,
            min_mother_bar_size=0,
            risk_reward_ratio=2.0,
            session_timezone="UTC",
            session_windows=["00:00-23:59"],
            trigger_must_be_within_session=False,
        )
        core = InsideBarCore(config)

        # Process complete pipeline
        signals = core.process_data(breakout_data, 'TEST')

        # Should have at least one signal
        assert len(signals) > 0

        # First signal should be BUY
        signal = signals[0]
        assert signal.side == 'BUY'

        # Entry should be mother bar high
        assert signal.entry_price == 103.0  # high of bar 1

        # SL should be mother bar low
        assert signal.stop_loss == 98.0  # low of bar 1

        # TP should be entry + (risk * RRR)
        risk = 103.0 - 98.0  # 5.0
        expected_tp = 103.0 + (risk * 2.0)  # 113.0
        assert signal.take_profit == expected_tp

    def test_no_signal_without_breakout(self):
        """Should NOT generate signal if no breakout occurs."""
        dates = pd.date_range('2025-01-01 14:00', periods=5, freq='5min', tz='UTC')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': [100, 101, 100.5, 101, 100.5],
            'high': [102, 103, 102.5, 102, 102],  # No breakout above 103
            'low': [99, 98, 99.5, 99, 99],
            'close': [101, 102, 101, 101, 101],
        })

        config = _cfg(min_mother_bar_size=0)
        core = InsideBarCore(config)

        signals = core.process_data(data, 'TEST')

        # Should have no signals (no breakout)
        assert len(signals) == 0

    def test_breakout_on_high_triggers_signal(self):
        """Breakout should trigger on high/low, not only close."""
        dates = pd.date_range('2025-01-01 14:00', periods=4, freq='5min', tz='UTC')
        # Bar 1 is mother, bar 2 is inside, bar 3 breaks above mother_high by high only.
        data = pd.DataFrame({
            'timestamp': dates,
            # mother (idx=1) body: 101-102, inside (idx=2) high/close inside body
            'open':  [100, 101, 101.0, 102.5],
            'high':  [102, 103, 101.8, 103.2],  # breakout by high
            'low':   [99,  98,  101.2, 101.8],
            'close': [101, 102, 101.5, 102.9],  # close below mother_high=103
        })

        config = _cfg(
            breakout_confirmation=True,
            min_mother_bar_size=0,
            risk_reward_ratio=2.0
        )
        core = InsideBarCore(config)

        signals = core.process_data(data, 'TEST')

        assert len(signals) > 0
        assert signals[0].side == 'BUY'


class TestRawSignalValidation:
    """Test RawSignal data validation."""

    def test_valid_buy_signal(self):
        """Valid BUY signal should pass validation."""
        signal = RawSignal(
            timestamp=pd.Timestamp('2025-01-01'),
            side='BUY',
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0
        )
        # Should not raise
        assert signal.side == 'BUY'

    def test_invalid_buy_sl_above_entry(self):
        """BUY signal with SL above entry should fail."""
        with pytest.raises(AssertionError):
            RawSignal(
                timestamp=pd.Timestamp('2025-01-01'),
                side='BUY',
                entry_price=100.0,
                stop_loss=105.0,  # SL above entry!
                take_profit=110.0
            )

    def test_valid_sell_signal(self):
        """Valid SELL signal should pass validation."""
        signal = RawSignal(
            timestamp=pd.Timestamp('2025-01-01'),
            side='SELL',
            entry_price=100.0,
            stop_loss=105.0,
            take_profit=90.0
        )
        assert signal.side == 'SELL'


def test_deterministic_behavior():
    """Same input MUST produce same output (determinism test)."""
    dates = pd.date_range('2025-01-01', periods=20, freq='5min')
    data = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.rand(20) * 10 + 100,
        'high': np.random.rand(20) * 10 + 105,
        'low': np.random.rand(20) * 10 + 95,
        'close': np.random.rand(20) * 10 + 100,
    })

    config = _cfg()
    core = InsideBarCore(config)

    # Run twice
    signals1 = core.process_data(data.copy(), 'TEST')
    signals2 = core.process_data(data.copy(), 'TEST')

    # MUST be identical
    assert len(signals1) == len(signals2)

    for s1, s2 in zip(signals1, signals2):
        assert s1.side == s2.side
        assert s1.entry_price == s2.entry_price
        assert s1.stop_loss == s2.stop_loss
        assert s1.take_profit == s2.take_profit
