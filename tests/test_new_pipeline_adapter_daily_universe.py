from __future__ import annotations

import pytest

from trading_dashboard.services.new_pipeline_adapter import NewPipelineAdapter


def test_daily_universe_runs_once_and_uses_symbol_all(monkeypatch):
    calls = {"count": 0, "kwargs": None}

    def _fake_run_pipeline(**kwargs):
        calls["count"] += 1
        calls["kwargs"] = kwargs
        raise RuntimeError("stop_after_capture")

    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.run_pipeline",
        _fake_run_pipeline,
    )
    monkeypatch.setattr(
        "trading_dashboard.services.new_pipeline_adapter.MarketdataStreamClient.is_configured",
        lambda self: False,
    )

    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    result = adapter.execute_backtest(
        run_name="daily_universe_once",
        strategy="ndx_momentum_rotation",
        symbols=["AAPL", "MSFT", "NVDA"],
        timeframe="D1",
        start_date="2025-01-01",
        end_date="2026-01-01",
        config_params={
            "strategy_version": "1.0.0",
            "session_timezone": "America/New_York",
            "session_mode": "raw",
            "timeframe_minutes": 1440,
            "topk": 5,
            "windows_months": [1, 3, 6, 12],
            "score_type": "sum_returns",
            "momentum_skip_mode": "none",
            "skip_last_n_weeks": None,
            "rebalance_equal_weight": False,
            "rebalance_frequency": "monthly",
            "regime_filter": "qqq_sma200",
            "risk_off_mode": "gate_only",
            "survivorship_mode": "current_members",
            "min_history_months": 12,
            "missing_data_policy": "FAIL_FAST",
            "sizing_mode": "EQUAL_WEIGHT",
            "cash_policy_on_gate_only": "HOLD_CASH",
            "daily_universe": "US",
            "daily_symbol_scope": "ALL",
            "fees_bps": 2.0,
            "slippage_bps": 1.0,
        },
    )

    assert result["status"] == "failed"
    assert calls["count"] == 1
    assert calls["kwargs"]["strategy_params"]["symbol"] == "ALL"
    assert calls["kwargs"]["strategy_params"]["daily_universe"] == "US"


def test_daily_universe_requires_ssot_keys():
    adapter = NewPipelineAdapter(progress_callback=lambda _: None)
    with pytest.raises(ValueError, match="missing SSOT keys"):
        adapter.execute_backtest(
            run_name="daily_universe_missing_keys",
            strategy="ndx_momentum_rotation",
            symbols=["AAPL", "MSFT"],
            timeframe="D1",
            start_date="2025-01-01",
            end_date="2026-01-01",
            config_params={
                "strategy_version": "1.0.0",
                "session_timezone": "America/New_York",
                "session_mode": "raw",
                "timeframe_minutes": 1440,
                "fees_bps": 2.0,
                "slippage_bps": 1.0,
            },
        )
