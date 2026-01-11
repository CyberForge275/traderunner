import pytest
from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore

def test_strategy_config_field_specs_api_contract():
    # Test valid strategy
    specs = StrategyConfigStore.get_field_specs("insidebar_intraday")
    
    assert "core" in specs
    assert "valid_from_policy" in specs["core"]
    
    val_spec = specs["core"]["valid_from_policy"]
    assert val_spec["kind"] == "enum"
    assert "signal_ts" in val_spec["options"]
    assert "next_bar" in val_spec["options"]

def test_strategy_config_field_specs_invalid_strategy():
    # Test unregistered strategy
    with pytest.raises(ValueError) as excinfo:
        StrategyConfigStore.get_field_specs("non_existent_strategy")
    
    assert "No manager registered" in str(excinfo.value)
