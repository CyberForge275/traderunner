import pytest

from trading_dashboard.callbacks.ssot_config_viewer_callback import _compute_overrides


def _call(original, value, section="tunable"):
    loaded_defaults = {
        "core": {},
        "tunable": {"some_int_param": original},
    }
    edited_values = [value]
    edited_ids = [{"section": section, "key": "some_int_param"}]
    return _compute_overrides(loaded_defaults, edited_values, edited_ids)


def test_int_accepts_string_float_with_integer_value():
    core, tunable = _call(1, "2.0")
    assert core == {}
    assert tunable["some_int_param"] == 2


def test_int_rejects_non_integer_string_float():
    with pytest.raises(ValueError):
        _call(1, "2.5")


def test_risk_reward_ratio_accepts_decimal_even_if_original_is_int():
    loaded_defaults = {
        "core": {"risk_reward_ratio": 2},
        "tunable": {},
    }
    edited_values = ["2.5"]
    edited_ids = [{"section": "core", "key": "risk_reward_ratio"}]

    core, tunable = _compute_overrides(loaded_defaults, edited_values, edited_ids)

    assert tunable == {}
    assert core["risk_reward_ratio"] == pytest.approx(2.5)
