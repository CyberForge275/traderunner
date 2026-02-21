import pytest

from axiom_bt.pipeline.config_resolver import resolve_config


def test_execution_policy_accepts_m1_probe_mode():
    defaults = {
        "execution": {
            "allow_same_bar_exit": True,
            "same_bar_resolution_mode": "no_fill",
            "intrabar_probe_timeframe": "M1",
        }
    }
    base = {
        "execution": {
            "same_bar_resolution_mode": "m1_probe_then_no_fill",
            "intrabar_probe_timeframe": "M1",
        }
    }
    result = resolve_config(base=base, overrides={}, defaults=defaults)
    execution = result.resolved["execution"]
    assert execution["same_bar_resolution_mode"] == "m1_probe_then_no_fill"
    assert execution["intrabar_probe_timeframe"] == "M1"


def test_execution_policy_rejects_invalid_mode():
    with pytest.raises(ValueError, match="same_bar_resolution_mode"):
        resolve_config(
            base={"execution": {"same_bar_resolution_mode": "foo"}},
            overrides={},
            defaults={},
        )


def test_execution_policy_rejects_non_m1_probe_timeframe():
    with pytest.raises(ValueError, match="intrabar_probe_timeframe"):
        resolve_config(
            base={"execution": {"intrabar_probe_timeframe": "M5"}},
            overrides={},
            defaults={},
        )
