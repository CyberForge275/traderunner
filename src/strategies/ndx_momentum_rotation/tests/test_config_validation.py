from __future__ import annotations

import pytest

from strategies.ndx_momentum_rotation.config import build_ndx_momentum_rotation_config


BASE = {
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


def test_config_builds() -> None:
    cfg = build_ndx_momentum_rotation_config(dict(BASE))
    assert cfg.topk == 5


def test_invalid_topk_fails() -> None:
    bad = dict(BASE)
    bad["topk"] = 0
    with pytest.raises(ValueError, match="topk"):
        build_ndx_momentum_rotation_config(bad)
