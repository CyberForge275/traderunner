#!/usr/bin/env python3
"""Verify backtest run artifacts invariants.

This script performs a lightweight sanity check on a single backtest run
directory under ``artifacts/backtests``. It validates that the core
manifests exist and that equity/metrics artifacts are present for
completed runs.

Usage examples (from repo root)::

    PYTHONPATH=src python scripts/verify_run_artifacts.py --run-id TEST_RUN
    PYTHONPATH=src python scripts/verify_run_artifacts.py --run-dir artifacts/backtests/TEST_RUN
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd


# Ensure project root is on sys.path so that ``src.*`` imports work
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[FAIL] Could not read JSON from {path}: {exc}")
        return {}


def verify_run_dir(run_dir: Path) -> int:
    """Verify invariants for a single run directory.

    Returns process exit code (0 = all checks passed, 1 = any failure).
    """

    failures: List[str] = []

    if not run_dir.exists() or not run_dir.is_dir():
        print(f"[FAIL] Run directory does not exist: {run_dir}")
        return 1

    print(f"[INFO] Verifying run artifacts in: {run_dir}")

    # Core manifests
    run_meta_path = run_dir / "run_meta.json"
    run_result_path = run_dir / "run_result.json"
    run_manifest_path = run_dir / "run_manifest.json"
    artifacts_index_path = run_dir / "artifacts_index.json"

    if not run_meta_path.exists():
        failures.append("Missing run_meta.json")
    if not run_result_path.exists():
        failures.append("Missing run_result.json")
    if not run_manifest_path.exists():
        failures.append("Missing run_manifest.json")

    run_result = _load_json(run_result_path) if run_result_path.exists() else {}
    status = str(run_result.get("status", "UNKNOWN")).upper()

    if status not in {"SUCCESS", "FAILED_PRECONDITION", "FAILED_POSTCONDITION", "ERROR"}:
        failures.append(f"Invalid run_result.status: {status!r}")

    # Artifacts index expectations: only for non-precondition failures.
    if status in {"SUCCESS", "FAILED_POSTCONDITION", "ERROR"} and not artifacts_index_path.exists():
        failures.append("Missing artifacts_index.json for completed run")

    # Equity expectations: for all non-precondition failures we expect an
    # equity_curve.csv file with at least one row.
    if status in {"SUCCESS", "FAILED_POSTCONDITION", "ERROR"}:
        equity_path = run_dir / "equity_curve.csv"
        if not equity_path.exists():
            failures.append("Missing equity_curve.csv for completed run")
        else:
            try:
                equity = pd.read_csv(equity_path)
                if equity.empty:
                    failures.append("equity_curve.csv is empty")
            except Exception as exc:  # pragma: no cover - defensive
                failures.append(f"Could not read equity_curve.csv: {exc}")

    # Metrics expectations: if metrics.json is present it must be valid JSON.
    metrics_path = run_dir / "metrics.json"
    if metrics_path.exists():
        _ = _load_json(metrics_path)

    if failures:
        print("[FAIL] Run artifacts verification FAILED:")
        for msg in failures:
            print(f"  - {msg}")
        return 1

    print("[OK] All core artifact invariants are satisfied.")
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify backtest run artifacts.")
    parser.add_argument("--run-dir", type=Path, help="Path to run directory")
    parser.add_argument("--run-id", type=str, help="Run identifier under artifacts/backtests")

    args = parser.parse_args(argv)

    if not args.run_dir and not args.run_id:
        parser.error("one of --run-dir or --run-id is required")

    if args.run_dir and args.run_id:
        parser.error("specify only one of --run-dir or --run-id")

    if args.run_dir:
        run_dir = args.run_dir
    else:
        # Resolve from settings
        from src.core.settings import get_settings

        settings = get_settings()
        run_dir = settings.backtests_dir / args.run_id

    return verify_run_dir(run_dir)


if __name__ == "__main__":  # pragma: no cover - manual utility
    raise SystemExit(main())
