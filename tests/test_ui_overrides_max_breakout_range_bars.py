from trading_dashboard.callbacks.ssot_config_viewer_callback import _compute_overrides


def _call(original, value, section="core"):
    loaded_defaults = {
        "core": {"max_breakout_range_bars": original},
        "tunable": {},
    }
    edited_values = [value]
    edited_ids = [{"section": section, "key": "max_breakout_range_bars"}]
    return _compute_overrides(loaded_defaults, edited_values, edited_ids)


def test_override_when_original_none_parses_integer():
    core, tunable = _call(None, "4")
    assert tunable == {}
    assert core["max_breakout_range_bars"] == 4


def test_empty_value_skips_optional_int_override():
    core, tunable = _call(None, "")
    assert tunable == {}
    assert core == {}
