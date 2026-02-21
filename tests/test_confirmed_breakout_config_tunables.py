from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore


def test_confirmed_breakout_defaults_accept_ratio_tunables():
    defaults = StrategyConfigStore.get_defaults("confirmed_breakout_intraday", "1.0.1")
    tunable = defaults.get("tunable", {})
    assert "mother_range_ratio_min" in tunable
    assert "mother_range_ratio_max" in tunable


def test_confirmed_breakout_field_specs_expose_ratio_tunables():
    specs = StrategyConfigStore.get_field_specs("confirmed_breakout_intraday")
    tunable = specs.get("tunable", {})
    assert tunable["mother_range_ratio_min"]["kind"] == "float"
    assert tunable["mother_range_ratio_max"]["kind"] == "float"
