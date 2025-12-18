"""Backtest data repository - query TradeRunner backtest artifacts.

This module reads run_log.json files and derived metrics for UI-triggered
backtests under artifacts/backtests/.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..config import BACKTESTS_DIR


@dataclass
class BacktestRun:
    """Lightweight representation of a single backtest run."""

    run_name: str
    created_at: Optional[datetime]
    finished_at: Optional[datetime]
    strategy: str
    timeframe: Optional[str]
    symbols: List[str]
    status: str

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.created_at and self.finished_at:
            return (self.finished_at - self.created_at).total_seconds()
        return None


def _safe_parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _iter_run_logs_legacy() -> List[BacktestRun]:
    """
    LEGACY: Iterate over runs using run_log.json (old pipeline).

    Only used if USE_LEGACY_DISCOVERY=1 is set.
    """

    runs: List[BacktestRun] = []
    root: Path = BACKTESTS_DIR
    if not root.exists():
        return runs

    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        # Skip raw runner directories here (we only care about UI runs)
        if entry.name.startswith("run_"):
            continue
        log_path = entry / "run_log.json"
        if not log_path.exists():
            continue
        try:
            with open(log_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue

        run_name = payload.get("run_name", entry.name)
        created_at = _safe_parse_dt(payload.get("created_at"))
        finished_at = _safe_parse_dt(payload.get("finished_at"))
        strategy = str(payload.get("strategy", "unknown"))
        timeframe = payload.get("timeframe")
        symbols = payload.get("symbols") or []
        status = str(payload.get("status", "unknown"))

        runs.append(
            BacktestRun(
                run_name=run_name,
                created_at=created_at,
                finished_at=finished_at,
                strategy=strategy,
                timeframe=timeframe,
                symbols=list(symbols),
                status=status,
            )
        )

    return runs


def _iter_run_logs() -> List[BacktestRun]:
    """
    Iterate over all backtest runs using RunDiscoveryService.

    New-pipeline runs (run_meta.json/run_manifest.json) now visible.
    Falls back to legacy discovery if USE_LEGACY_DISCOVERY=1.
    """

    # Legacy fallback for emergency rollback
    use_legacy = os.getenv("USE_LEGACY_DISCOVERY", "0") == "1"
    if use_legacy:
        logger = logging.getLogger(__name__)
        logger.warning("⚠️ Using LEGACY run discovery (USE_LEGACY_DISCOVERY=1)")
        return _iter_run_logs_legacy()

    # Use new RunDiscoveryService (manifest-based discovery)
    from trading_dashboard.services.run_discovery_service import RunDiscoveryService

    service = RunDiscoveryService()
    summaries = service.discover()

    # Convert BacktestRunSummary to BacktestRun for compatibility
    runs: List[BacktestRun] = []
    for summary in summaries:
        runs.append(
            BacktestRun(
                run_name=summary.run_id,
                created_at=summary.started_at,
                finished_at=summary.finished_at,
                strategy=summary.strategy_key,
                timeframe=summary.requested_tf,
                symbols=summary.symbols,
                status=summary.status.lower()
            )
        )

    return runs


def list_backtests(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    strategy: Optional[str] = None,
) -> pd.DataFrame:
    """Return a DataFrame of backtest runs for the dashboard.

    Columns:
        run_name, created_at, finished_at, duration_seconds, strategy,
        timeframe, symbols, status, created_at_display
    """

    runs = _iter_run_logs()
    if not runs:
        return pd.DataFrame(
            columns=[
                "run_name",
                "created_at",
                "finished_at",
                "duration_seconds",
                "strategy",
                "timeframe",
                "symbols",
                "status",
                "created_at_display",
            ]
        )

    records: List[Dict[str, Any]] = []
    for run in runs:
        created = run.created_at
        if start_date and created and created.date() < start_date:
            continue
        if end_date and created and created.date() > end_date:
            continue
        if strategy and run.strategy != strategy:
            continue

        created_display: str = ""
        if created is not None:
            created_display = created.astimezone().strftime("%Y-%m-%d %H:%M:%S")

        records.append(
            {
                "run_name": run.run_name,
                "created_at": created,
                "finished_at": run.finished_at,
                "duration_seconds": run.duration_seconds,
                "strategy": run.strategy,
                "timeframe": run.timeframe,
                "symbols": ",".join(run.symbols),
                "status": run.status,
                "created_at_display": created_display,
            }
        )

    if not records:
        return pd.DataFrame(
            columns=[
                "run_name",
                "created_at",
                "finished_at",
                "duration_seconds",
                "strategy",
                "timeframe",
                "symbols",
                "status",
                "created_at_display",
            ]
        )

    df = pd.DataFrame.from_records(records)
    if not df.empty and "created_at" in df.columns:
        df = df.sort_values("created_at", ascending=False)
    return df


def get_backtest_log(run_name: str) -> pd.DataFrame:
    """Return a normalized DataFrame of pipeline log entries for a run.

    Columns:
        kind, title, status, duration, details
    """

    root = BACKTESTS_DIR / run_name
    log_path = root / "run_log.json"
    if not log_path.exists():
        return pd.DataFrame(
            columns=["kind", "title", "status", "duration", "details"]
        )

    try:
        with open(log_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return pd.DataFrame(
            columns=["kind", "title", "status", "duration", "details"]
        )

    entries = payload.get("entries", [])
    rows: List[Dict[str, Any]] = []
    for entry in entries:
        kind = entry.get("kind", "")
        title = entry.get("title") or entry.get("phase") or kind
        status = entry.get("status", "")
        duration = entry.get("duration")
        details = (
            entry.get("message")
            or entry.get("command")
            or entry.get("details")
            or ""
        )

        rows.append(
            {
                "kind": kind,
                "title": title,
                "status": status,
                "duration": duration,
                "details": details,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=["kind", "title", "status", "duration", "details"]
        )

    df = pd.DataFrame.from_records(rows)
    return df


def get_backtest_metrics(run_name: str) -> Dict[str, Any]:
    """Return metrics.json contents for a run if available.

    The axiom_bt runner writes artifacts under either:

    - NEW: BACKTESTS_DIR / <run_id>
    - LEGACY: run_* directories with names like run_<ts>_<run_name>
    """

    runner_dir = _find_runner_dir(run_name)
    if runner_dir is None:
        return {}

    # Prefer artifacts_index.json when present
    index_path = runner_dir / "artifacts_index.json"
    metrics_path: Optional[Path] = None

    if index_path.exists():
        try:
            with open(index_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            for entry in payload.get("artifacts", []):
                if entry.get("kind") == "metrics" and entry.get("relpath"):
                    metrics_path = runner_dir / entry["relpath"]
                    break
        except (OSError, json.JSONDecodeError):
            metrics_path = None

    # Fallback to legacy metrics.json path
    if metrics_path is None:
        metrics_path = runner_dir / "metrics.json"

    if not metrics_path.exists():
        return {}

    try:
        with open(metrics_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _find_runner_dir(run_name: str) -> Optional[Path]:
    """Locate the axiom_bt runner directory for a given UI run name.

    Supports both new and legacy layouts:

    - NEW: BACKTESTS_DIR / <run_id> (run_id == run_name)
    - LEGACY: ``run_*_<run_name>`` directories created by the old runner
    """

    root = BACKTESTS_DIR
    if not root.exists():
        return None

    # New layout: direct directory match (run_id == run_name)
    direct = root / run_name
    if direct.exists() and direct.is_dir():
        return direct

    # Legacy layout: run_*_<run_name>
    for entry in root.iterdir():
        if not entry.is_dir() or not entry.name.startswith("run_"):
            continue
        if entry.name.endswith(run_name):
            return entry
    return None


def get_backtest_summary(run_name: str) -> Dict[str, Any]:
    """Return high-level summary for a run (status, strategy, timeframe, symbols)."""

    ui_dir = BACKTESTS_DIR / run_name
    summary: Dict[str, Any] = {
        "run_name": run_name,
        "status": "unknown",
        "strategy": "unknown",
        "timeframe": None,
        "symbols": [],
    }

    log_path = ui_dir / "run_log.json"
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            summary.update(
                {
                    "status": payload.get("status", summary["status"]),
                    "strategy": payload.get("strategy", summary["strategy"]),
                    "timeframe": payload.get("timeframe", summary["timeframe"]),
                    "symbols": payload.get("symbols", summary["symbols"]),
                }
            )
        except (OSError, json.JSONDecodeError):
            pass

    # Fallback to manifest if available
    runner_dir = _find_runner_dir(run_name)
    if runner_dir is not None:
        manifest_path = runner_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as handle:
                    manifest = json.load(handle)
                summary.setdefault("strategy", manifest.get("strategy", summary["strategy"]))
                summary.setdefault("timeframe", manifest.get("timeframe", summary["timeframe"]))
                summary.setdefault("symbols", manifest.get("symbols", summary["symbols"]))
            except (OSError, json.JSONDecodeError):
                pass

    return summary


def get_backtest_equity(run_name: str) -> pd.DataFrame:
    """Return equity_curve.csv as DataFrame if available."""

    runner_dir = _find_runner_dir(run_name)
    if runner_dir is None:
        return pd.DataFrame()

    # Prefer artifacts_index.json when present for deterministic discovery
    index_path = runner_dir / "artifacts_index.json"
    equity_path: Optional[Path] = None

    if index_path.exists():
        try:
            with open(index_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            artifacts = payload.get("artifacts") or []
            for entry in artifacts:
                if entry.get("kind") == "equity_curve" and entry.get("relpath"):
                    equity_path = runner_dir / entry["relpath"]
                    break
        except (OSError, json.JSONDecodeError):
            equity_path = None

    # Legacy fallback: direct equity_curve.csv lookup
    if equity_path is None:
        equity_path = runner_dir / "equity_curve.csv"

    if not equity_path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(equity_path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return pd.DataFrame()

    return df


def get_backtest_orders(run_name: str) -> Dict[str, pd.DataFrame]:
    """Return orders, fills and trades DataFrames for a run."""

    runner_dir = _find_runner_dir(run_name)
    if runner_dir is None:
        return {"orders": pd.DataFrame(), "fills": pd.DataFrame(), "trades": pd.DataFrame()}

    index_path = runner_dir / "artifacts_index.json"
    kind_to_path: Dict[str, Path] = {}

    if index_path.exists():
        try:
            with open(index_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            for entry in payload.get("artifacts", []):
                kind = entry.get("kind")
                relpath = entry.get("relpath")
                if kind and relpath:
                    kind_to_path[kind] = runner_dir / relpath
        except (OSError, json.JSONDecodeError):
            kind_to_path = {}

    def _read_csv(kind: str, legacy_name: str) -> pd.DataFrame:
        path = kind_to_path.get(kind) if kind_to_path else None
        if path is None:
            path = runner_dir / legacy_name
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
            return pd.DataFrame()

    return {
        "orders": _read_csv("orders", "orders.csv"),
        "fills": _read_csv("filled_orders", "filled_orders.csv"),
        "trades": _read_csv("trades", "trades.csv"),
    }


def get_rudometkin_candidates(run_name: str) -> pd.DataFrame:
    """Load latest Rudometkin daily candidates CSV for a run, if present.

    Mirrors the Streamlit `_load_rk_signals` helper.
    """

    root = BACKTESTS_DIR.parent.parent  # traderunner root
    rk_dir = root / "artifacts" / "signals" / run_name
    if not rk_dir.exists():
        return pd.DataFrame()

    csv_paths = sorted(rk_dir.glob("signals_rudometkin_*.csv"))
    if not csv_paths:
        return pd.DataFrame()

    latest = csv_paths[-1]
    try:
        df = pd.read_csv(latest)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return pd.DataFrame()

    df._source_path = latest  # type: ignore[attr-defined]
    return df

