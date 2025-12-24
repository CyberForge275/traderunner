from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtest.services.data_coverage import CoverageStatus, CoverageCheckResult, DateRange


def test_full_backtest_zero_orders_still_writes_equity(tmp_path, monkeypatch):
    """run_backtest_full must write a non-empty equity_curve.csv even with 0 orders.

    This protects the postcondition that full_backtest runs always produce
    an equity curve artifact, which is required both by the SSOT runner and
    by the dashboard repository layer.
    """

    from axiom_bt import full_backtest_runner as runner
    from backtest.services.run_status import RunStatus

    # Stub coverage check to always report SUFFICIENT, avoiding real parquet IO.
    def fake_check_coverage(symbol, timeframe, requested_end, lookback_days, auto_fetch=False):  # noqa: ARG001
        requested = DateRange(start=requested_end - pd.Timedelta(days=lookback_days), end=requested_end)
        return CoverageCheckResult(
            status=CoverageStatus.SUFFICIENT,
            requested_range=requested,
            cached_range=requested,
        )

    monkeypatch.setattr(runner, "check_coverage", fake_check_coverage)

    # Stub simulation to return completely empty equity/trades to mimic 0-orders case.
    def fake_simulate_insidebar_from_orders(**kwargs):  # type: ignore[override]
        # Ensure the adapter created an orders.csv for the engine call.
        orders_csv = Path(kwargs["orders_csv"])
        assert orders_csv.exists()
        empty_equity = pd.DataFrame(columns=["ts", "equity"])
        return {
            "equity": empty_equity,
            "filled_orders": pd.DataFrame(),
            "trades": pd.DataFrame(),
            "metrics": {},
            "orders": pd.DataFrame(),
        }

    monkeypatch.setattr(runner.replay_engine, "simulate_insidebar_from_orders", fake_simulate_insidebar_from_orders)

    run_id = "TEST_ZERO_ORDERS"
    requested_end = "2025-01-02"
    artifacts_root = tmp_path

    # Provide an explicit (empty) orders_source_csv so that this test focuses
    # solely on the equity postcondition behavior rather than the strategy
    # signal-detection path.
    orders_source = tmp_path / "prebuilt_orders.csv"
    pd.DataFrame(columns=["valid_from", "valid_to", "symbol", "side", "order_type", "price", "stop_loss", "take_profit"]).to_csv(orders_source, index=False)

    result = runner.run_backtest_full(
        run_id=run_id,
        symbol="APP",
        timeframe="M5",
        requested_end=requested_end,
        lookback_days=5,
        strategy_key="inside_bar",
        strategy_params={},
        artifacts_root=artifacts_root,
        market_tz="America/New_York",
        initial_cash=12345.0,
        costs=None,
        orders_source_csv=orders_source,
    )

    assert result.status == RunStatus.SUCCESS

    run_dir = artifacts_root / run_id
    equity_path = run_dir / "equity_curve.csv"
    assert equity_path.exists(), "equity_curve.csv must always be written for full_backtest runs"

    equity_df = pd.read_csv(equity_path)
    # Must contain at least one row with equity and ts columns
    assert not equity_df.empty
    assert "equity" in equity_df.columns
    assert "ts" in equity_df.columns
    # Drawdown column is computed when writing artifacts
    assert "drawdown_pct" in equity_df.columns
    # Flat curve: single point with initial cash and zero drawdown
    assert equity_df.loc[0, "equity"] == 12345.0
    assert equity_df.loc[0, "drawdown_pct"] == 0.0


def test_simulate_insidebar_from_orders_handles_unfillable_orders(tmp_path):
    """Replay engine must not crash when no equity points are produced.

    When orders exist but never result in entries/exits, the engine should
    still return a non-empty equity DataFrame with at least one point so
    that downstream code can always persist an equity curve.
    """

    from axiom_bt.engines import replay_engine

    orders_csv = tmp_path / "orders.csv"
    pd.DataFrame(
        [
            {
                "valid_from": "2025-01-01T10:00:00-05:00",
                "valid_to": "2025-01-01T10:05:00-05:00",
                "symbol": "NOPE",
                "side": "BUY",
                "order_type": "STOP",
                "price": 100.0,
                "stop_loss": 99.0,
                "take_profit": 102.0,
                "qty": 1,
            }
        ]
    ).to_csv(orders_csv, index=False)

    # Data path without any symbol parquet files ensures that no entries
    # or exits can be generated for the provided orders.
    empty_data_dir = tmp_path / "data_m5"
    empty_data_dir.mkdir()

    requested_end = "2025-12-17"

    result = replay_engine.simulate_insidebar_from_orders(
        orders_csv=orders_csv,
        data_path=empty_data_dir,
        tz="America/New_York",
        costs=replay_engine.Costs(fees_bps=0.0, slippage_bps=0.0),
        initial_cash=9999.0,
        requested_end=requested_end,
    )

    equity = result["equity"]
    assert isinstance(equity, pd.DataFrame)
    assert not equity.empty
    assert "ts" in equity.columns
    assert "equity" in equity.columns
    # With no fills/trades, equity should stay at initial_cash and the
    # timestamp must deterministically match the requested_end.
    assert float(equity.iloc[0]["equity"]) == 9999.0
    assert equity.iloc[0]["ts"] == pd.Timestamp(requested_end).tz_localize(
        "America/New_York"
    ).isoformat()
