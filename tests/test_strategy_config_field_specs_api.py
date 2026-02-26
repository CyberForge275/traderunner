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


def test_ui_field_specs_do_not_expose_max_position_loss_pct_equity_inside_bar():
    specs = StrategyConfigStore.get_field_specs("insidebar_intraday")
    assert "max_position_loss_pct_equity" not in specs.get("tunable", {})


def test_ui_field_specs_do_not_expose_max_position_loss_pct_equity_confirmed_breakout():
    specs = StrategyConfigStore.get_field_specs("confirmed_breakout_intraday")
    assert "max_position_loss_pct_equity" not in specs.get("tunable", {})


def test_session_timezone_is_dropdown_with_two_supported_values():
    specs = StrategyConfigStore.get_field_specs("insidebar_intraday")
    tz_spec = specs["core"]["session_timezone"]
    assert tz_spec["kind"] == "enum"
    assert sorted(tz_spec["options"]) == ["America/New_York", "Europe/Berlin"]


def test_harami_order_validity_policy_exposes_fixed_bars():
    specs = StrategyConfigStore.get_field_specs("harami_break_intraday")
    validity_spec = specs["core"]["order_validity_policy"]
    assert validity_spec["kind"] == "enum"
    assert sorted(validity_spec["options"]) == ["fixed_bars", "fixed_minutes", "session_end"]
    assert specs["core"]["timeframe_minutes"]["kind"] == "int"
    assert specs["core"]["strict_mode"]["kind"] == "bool"


def test_inside_bar_order_validity_policy_values():
    specs = StrategyConfigStore.get_field_specs("insidebar_intraday")
    validity_spec = specs["core"]["order_validity_policy"]
    assert sorted(validity_spec["options"]) == ["fixed_bars", "fixed_minutes", "session_end"]
