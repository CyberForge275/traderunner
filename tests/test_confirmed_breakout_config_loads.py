from axiom_bt.pipeline.strategy_config_loader import load_strategy_params_from_ssot


def test_confirmed_breakout_config_loads():
    cfg = load_strategy_params_from_ssot("confirmed_breakout_intraday", "1.0.0")

    assert cfg["strategy_id"] == "confirmed_breakout_intraday"
    assert cfg["version"] == "1.0.0"
    assert cfg["canonical_name"] == "confirmed_breakout"
    assert "inside_bar_definition_mode" in cfg["core"]
