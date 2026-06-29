from __future__ import annotations

import pytest

import strategies.config.managers  # noqa: F401 - trigger manager registration
from strategies.config.registry import config_manager_registry


def test_config_manager_loads_version() -> None:
    manager = config_manager_registry.get_manager("perlentaucher_daily_scan")
    cfg = manager.get("1.0.0")
    assert cfg["core"]["match_mode"] == "price_vol"
    assert cfg["core"]["min_history_days"] == 107


def test_invalid_match_mode_fails() -> None:
    manager = config_manager_registry.get_manager("perlentaucher_daily_scan")
    bad = manager.get("1.0.0")
    bad["core"]["match_mode"] = "invalid"
    with pytest.raises(ValueError, match="match_mode"):
        manager.validate("1.0.0", bad)


def test_invalid_timeframe_minutes_fails() -> None:
    manager = config_manager_registry.get_manager("perlentaucher_daily_scan")
    bad = manager.get("1.0.0")
    bad["core"]["timeframe_minutes"] = 5
    with pytest.raises(ValueError, match="timeframe_minutes"):
        manager.validate("1.0.0", bad)


def test_min_history_days_below_floor_fails() -> None:
    manager = config_manager_registry.get_manager("perlentaucher_daily_scan")
    bad = manager.get("1.0.0")
    bad["core"]["min_history_days"] = 90
    with pytest.raises(ValueError, match="min_history_days"):
        manager.validate("1.0.0", bad)
