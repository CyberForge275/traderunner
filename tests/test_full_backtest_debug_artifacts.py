from __future__ import annotations

from pathlib import Path
import json

import pandas as pd


def _make_dummy_intraday_frame() -> pd.DataFrame:
    idx = pd.date_range("2025-01-01 09:30", periods=50, freq="5min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
        },
        index=idx,
    )
    df.index.name = "timestamp"
    return df


def test_full_backtest_writes_debug_artifacts(tmp_path, monkeypatch):
    """run_backtest_full should emit core debug artifacts in debug/.

    This focuses on the in-process signal path (no external orders CSV)
    and stubs out I/O-heavy components so that we can assert only on
    artifact creation and basic structure.
    """

    from axiom_bt import full_backtest_runner as runner
    from backtest.services.run_status import RunStatus
    from backtest.services.data_coverage import CoverageStatus, CoverageCheckResult, DateRange

    # Stub coverage check to always report SUFFICIENT.
    def fake_check_coverage(symbol, timeframe, requested_end, lookback_days, auto_fetch=False):  # noqa: ARG001
        requested = DateRange(start=requested_end - pd.Timedelta(days=lookback_days), end=requested_end)
        return CoverageCheckResult(
            status=CoverageStatus.SUFFICIENT,
            requested_range=requested,
            cached_range=requested,
        )

    monkeypatch.setattr(runner, "check_coverage", fake_check_coverage)

    # Stub IntradayStore to avoid real parquet access.
    import axiom_bt.intraday as intraday_mod

    class DummyStore(intraday_mod.IntradayStore):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
            pass

        def ensure(self, *args, **kwargs):  # noqa: D401, ARG002
            return {"APP": ["noop"]}

        def load(self, symbol, timeframe, tz=None):  # noqa: D401, ARG002
            return _make_dummy_intraday_frame()

    monkeypatch.setattr(intraday_mod, "IntradayStore", DummyStore)

    # Stub simulation to avoid ReplayEngine dependency.
    def fake_simulate_insidebar_from_orders(**kwargs):  # type: ignore[override]
        equity = pd.DataFrame(
            [
                {"ts": "2025-01-02T00:00:00Z", "equity": 100000.0},
            ]
        )
        return {
            "equity": equity,
            "filled_orders": pd.DataFrame(),
            "trades": pd.DataFrame(),
            "metrics": {},
            "orders": pd.DataFrame(),
        }

    monkeypatch.setattr(runner.replay_engine, "simulate_insidebar_from_orders", fake_simulate_insidebar_from_orders)

    run_id = "DEBUG_ARTIFACTS_TEST"
    requested_end = "2025-01-02"
    artifacts_root = tmp_path

    result = runner.run_backtest_full(
        run_id=run_id,
        symbol="APP",
        timeframe="M5",
        requested_end=requested_end,
        lookback_days=5,
        strategy_key="inside_bar",
        strategy_params={"atr_period": 14},
        artifacts_root=artifacts_root,
        market_tz="America/New_York",
        initial_cash=100000.0,
        costs=None,
        orders_source_csv=None,
        debug_trace=True,
    )

    assert result.status == RunStatus.SUCCESS

    run_dir = artifacts_root / run_id
    debug_dir = run_dir / "debug"
    assert debug_dir.exists()

    # Core debug artifacts must exist
    assert (debug_dir / "data_sanity.json").exists()
    assert (debug_dir / "warmup_requirements.json").exists()
    assert (debug_dir / "inside_bar_trace.jsonl").exists()
    assert (debug_dir / "inside_bar_summary.json").exists()
    assert (debug_dir / "orders_debug.jsonl").exists()


def test_full_backtest_writes_diagnostics_even_without_debug(tmp_path, monkeypatch):
    """Diagnostics must be written even when debug_trace is disabled.

    This verifies that diagnostics.json and compact diagnostic steps are
    produced for the in-process signal path regardless of the debug flag.
    """

    from axiom_bt import full_backtest_runner as runner
    from backtest.services.run_status import RunStatus
    from backtest.services.data_coverage import CoverageStatus, CoverageCheckResult, DateRange

    # Stub coverage check to always report SUFFICIENT.
    def fake_check_coverage(symbol, timeframe, requested_end, lookback_days, auto_fetch=False):  # noqa: ARG001
        requested = DateRange(start=requested_end - pd.Timedelta(days=lookback_days), end=requested_end)
        return CoverageCheckResult(
            status=CoverageStatus.SUFFICIENT,
            requested_range=requested,
            cached_range=requested,
        )

    monkeypatch.setattr(runner, "check_coverage", fake_check_coverage)

    # Stub IntradayStore to avoid real parquet access.
    import axiom_bt.intraday as intraday_mod

    class DummyStore(intraday_mod.IntradayStore):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
            pass

        def ensure(self, *args, **kwargs):  # noqa: D401, ARG002
            return {"APP": ["noop"]}

        def load(self, symbol, timeframe, tz=None):  # noqa: D401, ARG002
            return _make_dummy_intraday_frame()

    monkeypatch.setattr(intraday_mod, "IntradayStore", DummyStore)

    # Stub simulation to avoid ReplayEngine dependency.
    def fake_simulate_insidebar_from_orders(**kwargs):  # type: ignore[override]
        equity = pd.DataFrame(
            [
                {"ts": "2025-01-02T00:00:00Z", "equity": 100000.0},
            ]
        )
        return {
            "equity": equity,
            "filled_orders": pd.DataFrame(),
            "trades": pd.DataFrame(),
            "metrics": {},
            "orders": pd.DataFrame(),
        }

    monkeypatch.setattr(runner.replay_engine, "simulate_insidebar_from_orders", fake_simulate_insidebar_from_orders)

    run_id = "DIAGNOSTICS_ALWAYS_ON_TEST"
    requested_end = "2025-01-02"
    artifacts_root = tmp_path

    result = runner.run_backtest_full(
        run_id=run_id,
        symbol="APP",
        timeframe="M5",
        requested_end=requested_end,
        lookback_days=5,
        strategy_key="inside_bar",
        strategy_params={"atr_period": 14},
        artifacts_root=artifacts_root,
        market_tz="America/New_York",
        initial_cash=100000.0,
        costs=None,
        orders_source_csv=None,
        debug_trace=False,
    )

    assert result.status == RunStatus.SUCCESS

    run_dir = artifacts_root / run_id

    # diagnostics.json must exist and contain data_sanity + warmup blocks
    diagnostics_path = run_dir / "diagnostics.json"
    assert diagnostics_path.exists()
    diag = json.loads(diagnostics_path.read_text())
    assert "data_sanity" in diag
    assert "warmup" in diag

    # run_steps.jsonl must contain compact diagnostic steps
    steps_path = run_dir / "run_steps.jsonl"
    assert steps_path.exists()
    step_lines = [json.loads(line) for line in steps_path.read_text().splitlines() if line.strip()]
    step_names = {entry.get("step_name") for entry in step_lines}
    assert "data_sanity" in step_names
    assert "warmup_check" in step_names
