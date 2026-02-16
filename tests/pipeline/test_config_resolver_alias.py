from axiom_bt.pipeline.config_resolver import resolve_config


def test_resolver_maps_fees_alias_to_commission_and_marks_derived():
    defaults = {"costs": {"slippage_bps": 0.0}}
    base = {"costs": {"fees_bps": 2.0}}

    result = resolve_config(base=base, overrides={}, defaults=defaults)

    assert result.resolved["costs"]["commission_bps"] == 2.0
    assert result.sources["costs.commission_bps"] == "base"
    assert result.resolved["costs"]["fees_bps"] == 2.0
    assert result.sources["costs.fees_bps"] == "derived"
