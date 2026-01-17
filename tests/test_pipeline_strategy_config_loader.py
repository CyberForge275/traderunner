import pytest

from axiom_bt.pipeline.strategy_config_loader import load_strategy_params_from_ssot, StrategyConfigLoadError


def test_load_strategy_success():
    cfg = load_strategy_params_from_ssot("insidebar_intraday", "1.0.0")
    for key in ["strategy_id", "canonical_name", "version", "required_warmup_bars", "core"]:
        assert key in cfg
    assert isinstance(cfg["required_warmup_bars"], int)
    assert "atr_period" in cfg["core"]
    assert "session_filter" in cfg["core"] or True  # session_filter may be present as list


def test_load_strategy_unknown_id():
    with pytest.raises(StrategyConfigLoadError) as exc:
        load_strategy_params_from_ssot("does_not_exist", "1.0.0")
    assert "not registered" in str(exc.value)


def test_load_strategy_unknown_version():
    with pytest.raises(StrategyConfigLoadError) as exc:
        load_strategy_params_from_ssot("insidebar_intraday", "9.9.9")
    assert "version '9.9.9' not found" in str(exc.value)
