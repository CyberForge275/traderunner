from __future__ import annotations

from pathlib import Path

from axiom_bt.pipeline.paths import get_artifacts_root, get_backtest_run_dir


def test_backtest_run_dir_uses_trading_artifacts_root(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "artifacts_root"
    monkeypatch.setenv("TRADING_ARTIFACTS_ROOT", str(root))
    monkeypatch.delenv("TRADERUNNER_ARTIFACTS_ROOT", raising=False)

    run_dir = get_backtest_run_dir("run_env_test")

    assert run_dir == root / "backtests" / "run_env_test"
    assert run_dir.exists()


def test_backtest_run_dir_defaults_to_repo_artifacts(monkeypatch) -> None:
    monkeypatch.delenv("TRADING_ARTIFACTS_ROOT", raising=False)
    monkeypatch.delenv("TRADERUNNER_ARTIFACTS_ROOT", raising=False)

    root = get_artifacts_root()
    run_dir = get_backtest_run_dir("run_default_test")

    assert root.name == "artifacts"
    assert run_dir.parent.name == "backtests"
    assert run_dir.parent.parent == root
