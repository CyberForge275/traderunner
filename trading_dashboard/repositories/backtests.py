"""Backtest data repository - query TradeRunner backtest artifacts.

This module reads run_log.json files and derived metrics for UI-triggered
backtests under artifacts/backtests/.
"""

from __future__ import annotations

import json
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


def _iter_run_logs() -> List[BacktestRun]:
    """Iterate over all UI-triggered backtest runs.

    UI runs live directly under BACKTESTS_DIR with names like
    ui_m5_APP_240d_10k and contain a run_log.json. The actual
    axiom_bt runner artifacts live in sibling run_* directories.
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

    The axiom_bt runner writes artifacts under run_* directories with
    names like: run_<ts>_<run_name>
    """

    root = BACKTESTS_DIR
    if not root.exists():
        return {}

    candidate: Optional[Path] = None
    for entry in root.iterdir():
        if not entry.is_dir() or not entry.name.startswith("run_"):
            continue
        if entry.name.endswith(run_name):
            candidate = entry
            break

    if candidate is None:
        return {}

    metrics_path = candidate / "metrics.json"
    if not metrics_path.exists():
        return {}

    try:
        with open(metrics_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _find_runner_dir(run_name: str) -> Optional[Path]:
    """Locate the axiom_bt runner directory for a given UI run name.

    Runner directories have the pattern ``run_*_<run_name>``.
    """

    root = BACKTESTS_DIR
    if not root.exists():
        return None

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

    path = runner_dir / "equity_curve.csv"
    if not path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return pd.DataFrame()

    return df


def get_backtest_orders(run_name: str) -> Dict[str, pd.DataFrame]:
    """Return orders, fills and trades DataFrames for a run."""

    runner_dir = _find_runner_dir(run_name)
    if runner_dir is None:
        return {"orders": pd.DataFrame(), "fills": pd.DataFrame(), "trades": pd.DataFrame()}

    def _read_csv(name: str) -> pd.DataFrame:
        p = runner_dir / name
        if not p.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(p)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
            return pd.DataFrame()

    return {
        "orders": _read_csv("orders.csv"),
        "fills": _read_csv("filled_orders.csv"),
        "trades": _read_csv("trades.csv"),
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

