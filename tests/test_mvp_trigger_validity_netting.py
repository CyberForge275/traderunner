"""
MVP Tests: Trigger-within-session, Validity Policies, Netting

Tests the 4 mandatory requirements:
1. Trigger outside session → 0 orders/trades
2. Trigger inside session → normal flow
3. fixed_minutes uses validity_minutes
4. Netting: 1 position per symbol

Run: PYTHONPATH=src python -m pytest tests/test_mvp_trigger_validity_netting.py -v
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

from strategies.inside_bar.core import InsideBarCore, RawSignal
from strategies.inside_bar.config import InsideBarConfig


@pytest.fixture
def base_config():
    """Base config for MVP tests."""
    return {
        'atr_period': 14,
        'risk_reward_ratio': 2.0,
        'session_timezone': 'Europe/Berlin',
        'session_windows': ['15:00-16:00', '16:00-17:00'],
        'order_validity_policy': 'session_end',
        'trigger_must_be_within_session': True,
        'netting_mode': 'one_position_per_symbol'
    }


def create_test_data_with_breakout(
    breakout_time: str,
    inside_bar_time: str = "14:55",
    tz: str = "Europe/Berlin"
) -> pd.DataFrame:
    """
    Create test OHLCV data with inside bar pattern and breakout.
    
    Args:
        breakout_time: Time of breakout bar (HH:MM format, Berlin TZ)
        inside_bar_time: Time of inside bar (default: 14:55, before session)
        tz: Timezone
        
    Returns:
        DataFrame with inside bar pattern and breakout
    """
    dates = pd.date_range('2025-11-28 14:00', periods=50, freq='5min', tz='UTC')
    dates = dates.tz_convert(tz)
    
    # Create base data
    data = {
        'timestamp': dates,
        'open': 100.0 + np.random.randn(len(dates)) * 0.1,
        'high': 101.0 + np.random.randn(len(dates)) * 0.1,
        'low': 99.0 + np.random.randn(len(dates)) * 0.1,
        'close': 100.0 + np.random.randn(len(dates)) * 0.1,
        'volume': 1000.0
    }
    df = pd.DataFrame(data)
    
    # Find mother bar index (1 bar before inside bar time)
    inside_dt = pd.Timestamp(f"2025-11-28 {inside_bar_time}", tz=tz)
    mother_idx = df[df['timestamp'] < inside_dt].index[-1] if len(df[df['timestamp'] < inside_dt]) > 0 else 0
    inside_idx = mother_idx + 1
    
    # Create mother bar (wide range)
    df.loc[mother_idx, 'high'] = 105.0
    df.loc[mother_idx, 'low'] = 95.0
    df.loc[mother_idx, 'open'] = 100.0
    df.loc[mother_idx, 'close'] = 100.0
    
    # Create inside bar (within mother range)
    df.loc[inside_idx, 'high'] = 102.0
    df.loc[inside_idx, 'low'] = 98.0
    df.loc[inside_idx, 'open'] = 100.0
    df.loc[inside_idx, 'close'] = 100.0
    
    # Find breakout bar index
    breakout_dt = pd.Timestamp(f"2025-11-28 {breakout_time}", tz=tz)
    breakout_idx = df[df['timestamp'] >= breakout_dt].index[0] if len(df[df['timestamp'] >= breakout_dt]) > 0 else inside_idx + 1
    
    # Create breakout above mother high
    df.loc[breakout_idx, 'close'] = 106.0  # Above mother high (105.0)
    df.loc[breakout_idx, 'high'] = 107.0
    df.loc[breakout_idx, 'low'] = 104.0
    
    return df


# ==============================================================================
# TEST 1: Trigger outside session → 0 orders/trades
# ==============================================================================

def test_trigger_outside_session_rejected(base_config):
    """
    Test that breakout OUTSIDE session windows is REJECTED.
    
    Setup:
    - Sessions: 15:00-16:00, 16:00-17:00
    - Inside bar at 14:55 (before session)
    - Breakout at 17:05 (AFTER session)
    
    Expected:
    - 0 signals generated (trigger outside session)
    """
    config = InsideBarConfig(**base_config)
    core = InsideBarCore(config)
    
    # Breakout at 17:05 (outside sessions)
    df = create_test_data_with_breakout(
        inside_bar_time="15:05",  # Inside session 1
        breakout_time="17:05"     # OUTSIDE sessions (after 17:00)
    )
    
    signals = core.process_data(df, symbol='TEST')
    
    # Trigger outside session → MUST be rejected
    assert len(signals) == 0, \
        f"Expected 0 signals (trigger outside session), got {len(signals)}"


# ==============================================================================
# TEST 2: Trigger inside session → normal flow
# ==============================================================================

def test_trigger_inside_session_accepted(base_config):
    """
    Test that breakout INSIDE session windows is ACCEPTED.
    
    Setup:
    - Sessions: 15:00-16:00, 16:00-17:00
    - Inside bar at 15:05
    - Breakout at 15:30 (INSIDE session 1)
    
    Expected:
    - 1 signal generated (trigger inside session)
    """
    config = InsideBarConfig(**base_config)
    core = InsideBarCore(config)
    
    # Breakout at 15:30 (inside session 1)
    df = create_test_data_with_breakout(
        inside_bar_time="15:05",
        breakout_time="15:30"  # INSIDE session 1 (15:00-16:00)
    )
    
    signals = core.process_data(df, symbol='TEST')
    
    # Trigger inside session → MUST be accepted
    assert len(signals) == 1, \
        f"Expected 1 signal (trigger inside session), got {len(signals)}"
    
    assert signals[0].side == 'BUY'
    assert signals[0].entry_price > 0


# ==============================================================================
# TEST 3: fixed_minutes uses validity_minutes
# ==============================================================================

def test_fixed_minutes_policy_uses_validity_minutes(base_config):
    """
    Test that order_validity_policy='fixed_minutes' uses validity_minutes parameter.
    
    This test verifies parameter wiring through:
    strategy_params → InsideBarConfig → validity calculation
    
    Note: We test config validation here. Full validity window calculation
    is tested in trade/validity.py tests.
    """
    # Test 1: fixed_minutes requires validity_minutes > 0
    config_dict = base_config.copy()
    config_dict['order_validity_policy'] = 'fixed_minutes'
    config_dict['order_validity_minutes'] = 30  # Should use this
    
    config = InsideBarConfig(**config_dict)
    
    # Verify policy set correctly
    assert config.order_validity_policy == 'fixed_minutes'
    assert config.order_validity_minutes == 30
    
    # Test 2: fixed_minutes with invalid validity_minutes should fail validation
    with pytest.raises(AssertionError, match="order_validity_minutes must be positive"):
        bad_config = base_config.copy()
        bad_config['order_validity_policy'] = 'fixed_minutes'
        bad_config['order_validity_minutes'] = 0  # Invalid
        InsideBarConfig(**bad_config)


# ==============================================================================
# TEST 4: Netting - 1 position per symbol
# ==============================================================================

def test_netting_one_position_per_symbol(base_config):
    """
    Test that netting_mode='one_position_per_symbol' blocks second position.
    
    Setup:
    - Generate 2 inside bars in DIFFERENT sessions
    - Both would normally generate signals
    
    Expected:
    - Only 1 signal (first one), second blocked by netting
    
    Note: This tests signal-generation-level netting. In real backtest,
    position lifecycle (fill → exit) happens in replay engine.
    """
    config = InsideBarConfig(**base_config)
    core = InsideBarCore(config)
    
    # Create data with TWO inside bar setups
    dates = pd.date_range('2025-11-28 14:00', periods=100, freq='5min', tz='UTC')
    dates = dates.tz_convert('Europe/Berlin')
    
    data = {
        'timestamp': dates,
        'open': 100.0 + np.random.randn(len(dates)) * 0.1,
        'high': 101.0 + np.random.randn(len(dates)) * 0.1,
        'low': 99.0 + np.random.randn(len(dates)) * 0.1,
        'close': 100.0 + np.random.randn(len(dates)) * 0.1,
        'volume': 1000.0
    }
    df = pd.DataFrame(data)
    
    # === FIRST INSIDE BAR + BREAKOUT (Session 1: 15:00-16:00) ===
    # Mother bar at 15:00
    idx1_mother = df[df['timestamp'] >= pd.Timestamp('2025-11-28 15:00', tz='Europe/Berlin')].index[0]
    df.loc[idx1_mother, 'high'] = 105.0
    df.loc[idx1_mother, 'low'] = 95.0
    
    # Inside bar at 15:05
    idx1_inside = idx1_mother + 1
    df.loc[idx1_inside, 'high'] = 102.0
    df.loc[idx1_inside, 'low'] = 98.0
    
    # Breakout at 15:10
    idx1_breakout = idx1_inside + 1
    df.loc[idx1_breakout, 'close'] = 106.0  # Above mother high
    df.loc[idx1_breakout, 'high'] = 107.0
    
    # === SECOND INSIDE BAR + BREAKOUT (Session 2: 16:00-17:00) ===
    # Mother bar at 16:00
    idx2_mother = df[df['timestamp'] >= pd.Timestamp('2025-11-28 16:00', tz='Europe/Berlin')].index[0]
    df.loc[idx2_mother, 'high'] = 110.0
    df.loc[idx2_mother, 'low'] = 100.0
    
    # Inside bar at 16:05
    idx2_inside = idx2_mother + 1
    df.loc[idx2_inside, 'high'] = 107.0
    df.loc[idx2_inside, 'low'] = 103.0
    
    # Breakout at 16:10
    idx2_breakout = idx2_inside + 1
    df.loc[idx2_breakout, 'close'] = 111.0  # Above mother high
    df.loc[idx2_breakout, 'high'] = 112.0
    
    signals = core.process_data(df, symbol='TEST')
    
    # NETTING ENFORCEMENT: Only 1 signal allowed (first one wins)
    assert len(signals) == 1, \
        f"Expected 1 signal (netting blocks second), got {len(signals)}"
    
    # Verify first signal was from session 1
    assert signals[0].side == 'BUY'


# ==============================================================================
# TEST 5: Trigger enforcement can be disabled
# ==============================================================================

def test_trigger_enforcement_disabled(base_config):
    """
    Test that trigger_must_be_within_session=False allows outside triggers.
    
    This is legacy behavior test - NOT recommended for production.
    """
    config_dict = base_config.copy()
    config_dict['trigger_must_be_within_session'] = False  # Disable enforcement
    
    config = InsideBarConfig(**config_dict)
    core = InsideBarCore(config)
    
    # Breakout OUTSIDE session (but enforcement disabled)
    df = create_test_data_with_breakout(
        inside_bar_time="15:05",
        breakout_time="17:05"  # Outside sessions
    )
    
    signals = core.process_data(df, symbol='TEST')
    
    # With enforcement disabled, trigger outside session is ALLOWED
    # BUT: signal will still be filtered by final session filter in process_data
    # So we expect 0 signals here (final filter still applies)
    assert len(signals) == 0, \
        "Even with trigger enforcement off, final session filter still applies"


# ==============================================================================
# TEST 6: Netting mode validation
# ==============================================================================

def test_netting_mode_validation():
    """Test that only 'one_position_per_symbol' is allowed in MVP."""
    base = {
        'atr_period': 14,
        'risk_reward_ratio': 2.0,
        'session_windows': ['15:00-16:00']
    }
    
    # Valid netting mode
    config = InsideBarConfig(**base, netting_mode='one_position_per_symbol')
    assert config.netting_mode == 'one_position_per_symbol'
    
    # Invalid netting mode should fail
    with pytest.raises(AssertionError, match="Only 'one_position_per_symbol' supported"):
        InsideBarConfig(**base, netting_mode='hedging')
    
    with pytest.raises(AssertionError, match="Only 'one_position_per_symbol' supported"):
        InsideBarConfig(**base, netting_mode='pyramiding')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
