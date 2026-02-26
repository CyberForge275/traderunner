from trading_dashboard.callbacks.ssot_config_viewer_callback import _compute_overrides


def test_trailing_nested_fields_are_reassembled_as_mapping():
    loaded_defaults = {
        "core": {
            "trailing": {
                "enabled": False,
                "trigger_tp_pct": 0.7,
                "risk_remaining_pct": 0.5,
                "apply_mode": "next_bar",
            }
        },
        "tunable": {},
    }
    edited_values = [["true"], "0.8", "0.4", "same_bar"]
    edited_ids = [
        {"section": "core", "key": "trailing.enabled"},
        {"section": "core", "key": "trailing.trigger_tp_pct"},
        {"section": "core", "key": "trailing.risk_remaining_pct"},
        {"section": "core", "key": "trailing.apply_mode"},
    ]

    core, tunable = _compute_overrides(loaded_defaults, edited_values, edited_ids)

    assert tunable == {}
    assert core["trailing"] == {
        "enabled": True,
        "trigger_tp_pct": 0.8,
        "risk_remaining_pct": 0.4,
        "apply_mode": "same_bar",
    }


def test_trailing_string_mapping_is_parsed_when_used_as_single_field():
    loaded_defaults = {
        "core": {"trailing": {"enabled": False, "trigger_tp_pct": 0.7, "risk_remaining_pct": 0.5, "apply_mode": "next_bar"}},
        "tunable": {},
    }
    edited_values = ['{"enabled": true, "trigger_tp_pct": 0.9, "risk_remaining_pct": 0.2, "apply_mode": "next_bar"}']
    edited_ids = [{"section": "core", "key": "trailing"}]

    core, tunable = _compute_overrides(loaded_defaults, edited_values, edited_ids)

    assert tunable == {}
    assert core["trailing"]["enabled"] is True
    assert core["trailing"]["trigger_tp_pct"] == 0.9
