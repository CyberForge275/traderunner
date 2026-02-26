from trading_dashboard.callbacks.ssot_config_viewer_callback import _compute_overrides


def test_stop_cap_atr_accepts_float_string_when_original_is_int():
    loaded_defaults = {
        "core": {"stop_cap_atr": 1},
        "tunable": {},
    }
    edited_values = ["0.5"]
    edited_ids = [{"section": "core", "key": "stop_cap_atr"}]

    core, tunable = _compute_overrides(loaded_defaults, edited_values, edited_ids)

    assert tunable == {}
    assert core["stop_cap_atr"] == 0.5
