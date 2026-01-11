import pytest
from src.strategies.config.specs.inside_bar_spec import InsideBarSpec

def test_inside_bar_spec_valid_from_policy_ok():
    spec = InsideBarSpec()
    
    # Valid values should pass
    valid_core = {
        "atr_period": 14,
        "risk_reward_ratio": 2.0,
        "min_mother_bar_size": 0.5,
        "breakout_confirmation": True,
        "inside_bar_mode": "inclusive",
        "session_timezone": "America/New_York",
        "session_filter": ["09:30-16:00"],
        "timeframe_minutes": 5,
        "valid_from_policy": "signal_ts"  # OK
    }
    spec.validate_core("1.0.0", valid_core)
    
    valid_core["valid_from_policy"] = "next_bar"  # OK
    spec.validate_core("1.0.0", valid_core)

def test_inside_bar_spec_valid_from_policy_invalid():
    spec = InsideBarSpec()
    
    invalid_core = {
        "atr_period": 14,
        "risk_reward_ratio": 2.0,
        "min_mother_bar_size": 0.5,
        "breakout_confirmation": True,
        "inside_bar_mode": "inclusive",
        "session_timezone": "America/New_York",
        "session_filter": ["09:30-16:00"],
        "timeframe_minutes": 5,
        "valid_from_policy": "foo"  # INVALID
    }
    
    with pytest.raises(ValueError) as excinfo:
        spec.validate_core("1.0.0", invalid_core)
    
    assert "invalid valid_from_policy: 'foo'" in str(excinfo.value)
    assert "allowed: signal_ts, next_bar" in str(excinfo.value)
