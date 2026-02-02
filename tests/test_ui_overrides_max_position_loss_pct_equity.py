import pytest

from trading_dashboard.callbacks.ssot_config_viewer_callback import _compute_overrides


def _call(original, value, section="tunable"):
    loaded_defaults = {
        "core": {},
        "tunable": {"max_position_loss_pct_equity": original},
    }
    edited_values = [value]
    edited_ids = [{"section": section, "key": "max_position_loss_pct_equity"}]
    return _compute_overrides(loaded_defaults, edited_values, edited_ids)


def test_override_from_int_to_float():
    core, tunable = _call(0, 0.3)
    assert core == {}
    assert tunable["max_position_loss_pct_equity"] == pytest.approx(0.3)


def test_override_from_comma_string():
    core, tunable = _call(0, "0,03")
    assert core == {}
    assert tunable["max_position_loss_pct_equity"] == pytest.approx(0.03)


def test_override_from_dot_string():
    core, tunable = _call(0.01, "0.03")
    assert core == {}
    assert tunable["max_position_loss_pct_equity"] == pytest.approx(0.03)


def test_none_value_skips_override():
    core, tunable = _call(0.01, None)
    assert core == {}
    assert tunable == {}


def test_empty_string_skips_override():
    core, tunable = _call(0.01, "")
    assert core == {}
    assert tunable == {}
