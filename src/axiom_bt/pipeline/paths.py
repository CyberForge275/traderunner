from __future__ import annotations

import os
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_artifacts_root() -> Path:
    root = (
        os.getenv("TRADING_ARTIFACTS_ROOT")
        or os.getenv("TRADERUNNER_ARTIFACTS_ROOT")
    )
    if root:
        return Path(root).expanduser()
    return _PROJECT_ROOT / "artifacts"


def get_backtests_root() -> Path:
    backtests = get_artifacts_root() / "backtests"
    backtests.mkdir(parents=True, exist_ok=True)
    return backtests


def get_backtest_run_dir(run_id: str) -> Path:
    run_dir = get_backtests_root() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir

