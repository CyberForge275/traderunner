from __future__ import annotations

import pandas as pd
import pytest

import strategies.config.managers  # noqa: F401 - trigger manager registration
from strategies.config.registry import config_manager_registry
from strategies.ndx_momentum_rotation.plugin import NdxMomentumRotationPlugin
from strategies.registry import get_strategy


def test_schema_loads() -> None:
    schema = NdxMomentumRotationPlugin.get_schema("1.0.0")
    assert schema.strategy_id == "ndx_momentum_rotation"


def test_extend_signal_frame_fails_for_single_symbol() -> None:
    bars = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC"),
            "symbol": ["AAPL", "AAPL", "AAPL"],
            "open": [1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0],
            "volume": [1.0, 1.0, 1.0],
        }
    )
    params = {
        "session_timezone": "America/New_York",
        "session_mode": "raw",
        "timeframe_minutes": 1440,
        "daily_universe": "US",
        "daily_symbol_scope": "ALL",
        "topk": 5,
        "windows_months": [1, 3, 6, 12],
        "score_type": "sum_returns",
        "momentum_skip_mode": "none",
        "rebalance_equal_weight": False,
        "rebalance_frequency": "monthly",
        "regime_filter": "qqq_sma200",
        "risk_off_mode": "gate_only",
        "survivorship_mode": "current_members",
        "min_history_months": 12,
        "missing_data_policy": "FAIL_FAST",
        "sizing_mode": "EQUAL_WEIGHT",
        "cash_policy_on_gate_only": "HOLD_CASH",
    }

    with pytest.raises(RuntimeError, match="multi-symbol"):
        NdxMomentumRotationPlugin.extend_signal_frame(bars, params)


def test_strategy_registry_lookup_works() -> None:
    plugin = get_strategy("ndx_momentum_rotation")
    assert plugin.strategy_id == "ndx_momentum_rotation"


def test_config_manager_registry_lookup_works() -> None:
    manager = config_manager_registry.get_manager("ndx_momentum_rotation")
    assert manager is not None


def test_extend_signal_frame_preserves_row_count_for_multi_symbol() -> None:
    bars = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:00:00Z",
                    "2026-01-02T00:00:00Z",
                    "2026-01-02T00:00:00Z",
                ],
                utc=True,
            ),
            "symbol": ["AAPL", "MSFT", "AAPL", "MSFT"],
            "open": [1.0, 2.0, 1.1, 2.1],
            "high": [1.0, 2.0, 1.1, 2.1],
            "low": [1.0, 2.0, 1.1, 2.1],
            "close": [1.0, 2.0, 1.1, 2.1],
            "volume": [10.0, 20.0, 11.0, 21.0],
        }
    )
    params = {
        "session_timezone": "America/New_York",
        "session_mode": "raw",
        "timeframe_minutes": 1440,
        "daily_universe": "US",
        "daily_symbol_scope": "ALL",
        "topk": 5,
        "windows_months": [1, 3, 6, 12],
        "score_type": "sum_returns",
        "momentum_skip_mode": "none",
        "rebalance_equal_weight": False,
        "rebalance_frequency": "monthly",
        "regime_filter": "qqq_sma200",
        "risk_off_mode": "gate_only",
        "survivorship_mode": "current_members",
        "min_history_months": 12,
        "missing_data_policy": "FAIL_FAST",
        "sizing_mode": "EQUAL_WEIGHT",
        "cash_policy_on_gate_only": "HOLD_CASH",
    }

    out = NdxMomentumRotationPlugin.extend_signal_frame(bars, params)
    assert len(out) == len(bars)


def test_generate_intent_returns_pipeline_contract_artifacts() -> None:
    signals = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-01-01T00:00:00Z"], utc=True),
            "symbol": ["AAPL"],
        }
    )
    out = NdxMomentumRotationPlugin.generate_intent(
        signals,
        "ndx_momentum_rotation",
        "1.0.0",
        params={},
    )
    assert hasattr(out, "events_intent")
    assert hasattr(out, "signals_frame")
    assert hasattr(out, "intent_hash")
