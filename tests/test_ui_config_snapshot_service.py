import pytest

from trading_dashboard.services.backtest_ui.config_snapshot_service import (
    SnapshotValidationError,
    build_config_params_from_snapshot,
    resolve_insidebar_snapshot,
)


def test_snapshot_is_never_reused_even_same_strategy_version(monkeypatch):
    snapshot = {
        "strategy_id": "insidebar_intraday",
        "version": "1.0.1",
        "required_warmup_bars": 40,
        "core": {"atr_period": 8},
        "tunable": {"lookback_candles": 50},
        "strategy_finalized": True,
    }
    calls = {"n": 0}

    def _fake_defaults(strategy_id, version):
        calls["n"] += 1
        assert strategy_id == "insidebar_intraday"
        assert version == "1.0.1"
        return {
            "required_warmup_bars": 40,
            "core": {"session_filter": ["09:30-11:00", "14:00-15:00"]},
            "tunable": {"lookback_candles": 50},
            "strategy_finalized": False,
        }

    monkeypatch.setattr(
        "trading_dashboard.config_store.strategy_config_store.StrategyConfigStore.get_defaults",
        _fake_defaults,
    )

    resolved = resolve_insidebar_snapshot(
        strategy_id="insidebar_intraday",
        selected_version="1.0.1",
        snapshot=snapshot,
    )
    resolved["core"]["session_filter"] = ["CHANGED"]
    reloaded = resolve_insidebar_snapshot(
        strategy_id="insidebar_intraday",
        selected_version="1.0.1",
        snapshot=resolved,
    )
    assert resolved["version"] == "1.0.1"
    assert reloaded["version"] == "1.0.1"
    assert reloaded["core"]["session_filter"] == ["09:30-11:00", "14:00-15:00"]
    assert reloaded is not resolved
    assert calls["n"] == 2


def test_resolve_insidebar_snapshot_reloads_when_version_changed(monkeypatch):
    snapshot = {
        "strategy_id": "insidebar_intraday",
        "version": "1.0.1",
        "required_warmup_bars": 40,
        "core": {"session_filter": ["09:30-11:00", "14:00-15:00"]},
        "tunable": {"lookback_candles": 50},
        "strategy_finalized": False,
    }

    def _fake_defaults(strategy_id, version):
        assert strategy_id == "insidebar_intraday"
        assert version == "1.0.3"
        return {
            "required_warmup_bars": 40,
            "core": {"session_filter": ["09:30-14:00"], "timeframe_minutes": 15},
            "tunable": {"lookback_candles": 50},
            "strategy_finalized": False,
        }

    monkeypatch.setattr(
        "trading_dashboard.config_store.strategy_config_store.StrategyConfigStore.get_defaults",
        _fake_defaults,
    )

    resolved = resolve_insidebar_snapshot(
        strategy_id="insidebar_intraday",
        selected_version="1.0.3",
        snapshot=snapshot,
    )
    assert resolved["version"] == "1.0.3"
    assert resolved["core"]["session_filter"] == ["09:30-14:00"]
    assert resolved["core"]["timeframe_minutes"] == 15


def test_resolve_insidebar_snapshot_loads_defaults_when_snapshot_missing(monkeypatch):
    def _fake_defaults(strategy_id, version):
        assert strategy_id == "insidebar_intraday"
        assert version == "1.0.2"
        return {
            "required_warmup_bars": 40,
            "core": {"atr_period": 10},
            "tunable": {"lookback_candles": 60},
            "strategy_finalized": False,
        }

    monkeypatch.setattr(
        "trading_dashboard.config_store.strategy_config_store.StrategyConfigStore.get_defaults",
        _fake_defaults,
    )

    resolved = resolve_insidebar_snapshot(
        strategy_id="insidebar_intraday",
        selected_version="1.0.2",
        snapshot=None,
    )
    assert resolved["strategy_id"] == "insidebar_intraday"
    assert resolved["version"] == "1.0.2"
    assert resolved["core"]["atr_period"] == 10


def test_resolve_insidebar_snapshot_raises_when_no_selected_version():
    with pytest.raises(SnapshotValidationError, match="Configuration snapshot missing"):
        resolve_insidebar_snapshot(
            strategy_id="insidebar_intraday",
            selected_version=None,
            snapshot=None,
        )


def test_build_config_params_from_snapshot_compound_off():
    snapshot = {"core": {"a": 1}, "tunable": {"b": 2}}
    cfg = build_config_params_from_snapshot(
        strategy="insidebar_intraday",
        version_to_use="1.0.0",
        snapshot=snapshot,
        compound_toggle_val=[],
        equity_basis_val="cash_only",
    )
    assert cfg["a"] == 1
    assert cfg["b"] == 2
    assert cfg["strategy_version"] == "1.0.0"
    assert "backtesting" not in cfg


def test_build_config_params_from_snapshot_compound_on_defaults_basis():
    cfg = build_config_params_from_snapshot(
        strategy="insidebar_intraday",
        version_to_use="1.0.0",
        snapshot={},
        compound_toggle_val=["enabled"],
        equity_basis_val=None,
    )
    assert cfg["backtesting"]["compound_sizing"] is True
    assert cfg["backtesting"]["compound_equity_basis"] == "cash_only"


def test_build_config_params_from_snapshot_supports_confirmed_breakout():
    snapshot = {
        "core": {"atr_period": 8},
        "tunable": {"lookback_candles": 50},
    }
    cfg = build_config_params_from_snapshot(
        strategy="confirmed_breakout_intraday",
        version_to_use="1.0.0",
        snapshot=snapshot,
        compound_toggle_val=[],
        equity_basis_val="cash_only",
    )
    assert cfg["atr_period"] == 8
    assert cfg["lookback_candles"] == 50
    assert cfg["strategy_version"] == "1.0.0"
