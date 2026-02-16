import pytest

from axiom_bt.pipeline.config_resolver import resolve_config


def test_resolver_uses_defaults_when_costs_not_overridden():
    defaults = {"costs": {"commission_bps": 0.0, "slippage_bps": 0.0}}

    result = resolve_config(base={}, overrides={}, defaults=defaults)

    assert result.resolved["costs"]["commission_bps"] == 0.0
    assert result.resolved["costs"]["slippage_bps"] == 0.0
    assert result.sources["costs.commission_bps"] == "default"
    assert result.sources["costs.slippage_bps"] == "default"


def test_resolver_validates_negative_costs():
    defaults = {"costs": {"commission_bps": 0.0, "slippage_bps": 0.0}}
    base = {"costs": {"commission_bps": -1.0}}

    with pytest.raises(ValueError, match="commission_bps"):
        resolve_config(base=base, overrides={}, defaults=defaults)
