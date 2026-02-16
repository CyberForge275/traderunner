from axiom_bt.pipeline.config_resolver import resolve_config


def test_resolver_precedence_defaults_base_ui_cli_spyder():
    defaults = {"costs": {"commission_bps": 0.0, "slippage_bps": 0.0}}
    base = {"costs": {"commission_bps": 1.0}}
    overrides = {
        "ui": {"costs": {"commission_bps": 2.0}},
        "cli": {"costs": {"commission_bps": 3.0}},
        "spyder": {"costs": {"commission_bps": 4.0}},
    }

    result = resolve_config(base=base, overrides=overrides, defaults=defaults)

    assert result.resolved["costs"]["commission_bps"] == 4.0
    assert result.sources["costs.commission_bps"] == "spyder"
