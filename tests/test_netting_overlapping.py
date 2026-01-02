"""
Test that netting blocks OVERLAPPING positions (same or overlapping sessions).

This test demonstrates the corrected netting semantics:
- Session 1 signal at 15:30 with session_end validity → netting_open_until = 16:00
- Attempt second signal at 15:45 (BEFORE netting_open_until) → BLOCKED
"""
import pytest
import pandas as pd
import numpy as np

from strategies.inside_bar.core import InsideBarCore
from strategies.inside_bar.config import InsideBarConfig


def test_netting_blocks_overlapping_within_session():
    """Test that netting blocks overlapping positions within same session."""
    config = InsideBarConfig(
        atr_period=14,
        risk_reward_ratio=2.0,
        session_timezone='Europe/Berlin',
        session_windows=['15:00-17:00'],  # Single long session
        order_validity_policy='session_end',  # Valid until 17:00
        trigger_must_be_within_session=True,
        netting_mode='one_position_per_symbol'
    )
    
    core = InsideBarCore(config)
    
    # Create data with TWO inside bar patterns in SAME session
    dates = pd.date_range('2025-11-28 14:50', periods=30, freq='5min', tz='UTC')
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
    
    # FIRST pattern at 15:25-15:30
    idx1_mother = df[df['timestamp'] >= pd.Timestamp('2025-11-28 15:25', tz='Europe/Berlin')].index[0]
    df.loc[idx1_mother, ['high', 'low', 'open', 'close']] = [105.0, 95.0, 100.0, 100.0]
    
    idx1_inside = idx1_mother + 1
    df.loc[idx1_inside, ['high', 'low', 'open', 'close']] = [102.0, 98.0, 100.0, 100.0]
    
    idx1_breakout = idx1_inside + 1  # 15:35
    df.loc[idx1_breakout, ['close', 'high', 'low']] = [106.0, 107.0, 104.0]
    
    # SECOND pattern at 15:50-15:55 (OVERLAPS with first position window ending at 17:00)
    idx2_mother = df[df['timestamp'] >= pd.Timestamp('2025-11-28 15:50', tz='Europe/Berlin')].index[0]
    df.loc[idx2_mother, ['high', 'low', 'open', 'close']] = [110.0, 100.0, 105.0, 105.0]
    
    idx2_inside = idx2_mother + 1
    df.loc[idx2_inside, ['high', 'low', 'open', 'close']] = [107.0, 103.0, 105.0, 105.0]
    
    idx2_breakout = idx2_inside + 1  # 16:00
    df.loc[idx2_breakout, ['close', 'high', 'low']] = [111.0, 112.0, 109.0]
    
    signals = core.process_data(df, symbol='TEST')
    
    # First signal at ~15:35 → netting_open_until = 17:00 (session_end)
    # Second trigger at ~16:00 < 17:00 → BLOCKED
    assert len(signals) == 1, \
        f"Expected 1 signal (second blocked by netting), got {len(signals)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
