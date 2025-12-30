from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def test_equity_loads_from_artifacts_index(tmp_path, monkeypatch):
    """Backtest repository must prefer artifacts_index.json when present.

    This ensures new FULL_BACKTEST runs discovered via the index are
    correctly surfaced to the dashboard without relying on legacy
    filename heuristics.
    """

    from trading_dashboard.repositories import backtests

    # Arrange: create a fake run directory with equity + artifacts_index
    run_name = "TEST_RUN_INDEX_FIRST"
    run_dir = tmp_path / run_name
    run_dir.mkdir(parents=True)

    equity = pd.DataFrame(
        [
            {"ts": "2025-01-01T10:00:00Z", "equity": 10000.0, "drawdown_pct": 0.0},
            {"ts": "2025-01-01T10:05:00Z", "equity": 10050.0, "drawdown_pct": 0.0},
        ]
    )
    equity.to_csv(run_dir / "equity_curve.csv", index=False)

    index_payload = {
        "artifacts": [
            {
                "kind": "equity_curve",
                "relpath": "equity_curve.csv",
                "format": "csv",
                "rows": len(equity),
                "schema": list(equity.columns),
            }
        ],
        "indexed_at": "2025-01-01T12:00:00Z",
    }
    (run_dir / "artifacts_index.json").write_text(json.dumps(index_payload, indent=2), encoding="utf-8")

    # Point repository BACKTESTS_DIR at our tmp_path root
    monkeypatch.setattr(backtests, "BACKTESTS_DIR", tmp_path)

    # Act
    df = backtests.get_backtest_equity(run_name)

    # Assert: index-first discovery should return our equity frame
    assert not df.empty
    assert list(df.columns) == list(equity.columns)
    assert len(df) == len(equity)


def test_equity_fallback_without_index(tmp_path, monkeypatch):
    """Repository must fall back to legacy equity_curve.csv when no index exists."""

    from trading_dashboard.repositories import backtests

    run_name = "TEST_RUN_LEGACY"
    run_dir = tmp_path / run_name
    run_dir.mkdir(parents=True)

    equity = pd.DataFrame(
        [
            {"ts": "2025-01-02T10:00:00Z", "equity": 9000.0, "drawdown_pct": -5.0},
        ]
    )
    equity.to_csv(run_dir / "equity_curve.csv", index=False)

    # No artifacts_index.json on purpose (legacy case)
    monkeypatch.setattr(backtests, "BACKTESTS_DIR", tmp_path)

    df = backtests.get_backtest_equity(run_name)

    assert not df.empty
    assert list(df.columns) == list(equity.columns)
    assert len(df) == len(equity)
