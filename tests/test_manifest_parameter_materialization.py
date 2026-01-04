"""
Test to verify that order_validity_policy appears in run metadata and manifests.

This ensures strategy parameters are properly materialized for audit/versioning.
"""
import pytest
from pathlib import Path
from src.strategies.inside_bar.config import load_default_config


def test_order_validity_policy_in_yaml_defaults():
    """Test that order_validity_policy is present in the strategy YAML defaults."""
    config = load_default_config()
    
    assert 'order_validity_policy' in config, \
        "order_validity_policy must be present in strategy YAML for manifest materialization"
    
    assert config['order_validity_policy'] == 'session_end', \
        "Default order_validity_policy should be 'session_end'"


def test_all_critical_params_materialize():
    """Test that all audit-critical parameters are present in loaded config."""
    config = load_default_config()
    
    critical_params = [
        'order_validity_policy',
        'max_position_pct',
        'stop_distance_cap_ticks',
        'risk_reward_ratio',
        'atr_period'
    ]
    
    for param in critical_params:
        assert param in config, \
            f"Critical parameter '{param}' missing from config - needed for run manifest audit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
