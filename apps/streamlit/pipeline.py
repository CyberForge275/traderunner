from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))
os.environ.setdefault("PYTHONPATH", str(SRC))

BT_DIR = ROOT / "artifacts" / "backtests"
LOGS_DIR = ROOT / "artifacts" / "logs"

from core.settings import DEFAULT_INITIAL_CASH
from state import FetchConfig, PipelineConfig
from strategies import factory, registry, strategy_hooks


_LOG_ENTRIES: List[dict] = []


def _store_log(entry: dict) -> None:
    """Append a log entry to the in-memory and session log buffers."""
    _LOG_ENTRIES.append(entry)
    try:
        log = st.session_state.setdefault("pipeline_log", [])
        log.append(entry)
    except Exception:  # pragma: no cover - defensive
        # Keep logging best-effort; don't break pipeline on UI/session issues.
        pass


def get_pipeline_log() -> List[dict]:
    """Return a copy of the in-memory pipeline log for persistence/analysis."""
    return list(_LOG_ENTRIES)


def _set_last_duration(value: float) -> None:
    st.session_state["pipeline_last_duration"] = value


def _get_last_duration() -> float | None:
    return st.session_state.pop("pipeline_last_duration", None)


def _format_command(cmd: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def _combine_output(stdout: str | None, stderr: str | None) -> str:
    parts = []
    if stdout:
        parts.append(stdout.strip())
    if stderr:
        parts.append(stderr.strip())
    return "\n".join(part for part in parts if part)


def show_step(title: str, cmd: List[str], rc: int, output: str, *, raise_on_error: bool = True) -> None:
    status = "success"
    if rc != 0:
        status = "error" if raise_on_error else "warning"
    _store_log({
        "kind": "command",
        "title": title,
        "command": _format_command(cmd),
        "return_code": rc,
        "output": output,
        "status": status,
        "duration": _get_last_duration(),
    })
    with st.expander(title, expanded=True):
        st.code(_format_command(cmd) or "(no command)")
        if rc == 0:
            st.success("OK")
        elif raise_on_error:
            st.error(f"[ERROR] rc={rc}")
        else:
            st.warning(f"[WARN] rc={rc}")
        if output:
            st.text(output)
    if rc != 0 and raise_on_error:
        raise RuntimeError(title)


def show_step_message(title: str, message: str, status: str = "info") -> None:
    _store_log({
        "kind": "message",
        "title": title,
        "message": message,
        "status": status,
        "duration": _get_last_duration(),
    })
    with st.expander(title, expanded=True):
        st.code("(skipped)")
        display = getattr(st, status, st.info)
        display(message)


def run_cli_step(
    title: str,
    module_args: List[str],
    *,
    raise_on_error: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    cmd = [sys.executable, "-m", *module_args]
    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    duration = time.perf_counter() - start
    _set_last_duration(duration)
    output = _combine_output(result.stdout, result.stderr)
    show_step(title, cmd, result.returncode, output, raise_on_error=raise_on_error)
    return result


def _resolve_initial_cash(pipeline: PipelineConfig) -> float:
    if pipeline.config_payload and "initial_cash" in pipeline.config_payload:
        try:
            return float(pipeline.config_payload["initial_cash"])
        except (TypeError, ValueError):
            pass
    if pipeline.config_path:
        try:
            with open(pipeline.config_path, "r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle)
            if isinstance(payload, dict) and "initial_cash" in payload:
                return float(payload["initial_cash"])
        except (OSError, yaml.YAMLError, ValueError, TypeError):
            pass
    default_cash = pipeline.strategy.default_payload.get("initial_cash", DEFAULT_INITIAL_CASH)
    try:
        return float(default_cash)
    except (TypeError, ValueError):
        return DEFAULT_INITIAL_CASH


def _build_sizing_args(
    pipeline: PipelineConfig,
    equity_value: float,
    risk_pct_override: Optional[float] = None,
) -> List[str]:
    sizing_cfg = dict(pipeline.strategy.default_sizing or {})
    if risk_pct_override is not None:
        sizing_cfg["mode"] = "risk"
        sizing_cfg["risk_pct"] = risk_pct_override

    mode = sizing_cfg.get("mode")
    args: List[str] = []
    if mode == "risk":
        args.extend(["--sizing", "risk", "--equity", f"{equity_value:.2f}"])
        risk_pct = sizing_cfg.get("risk_pct")
        if risk_pct is not None:
            args.extend(["--risk-pct", str(risk_pct)])
        max_notional = sizing_cfg.get("max_notional", equity_value)
        args.extend(["--max-notional", f"{float(max_notional):.2f}"])
        min_qty = sizing_cfg.get("min_qty")
        if min_qty is not None:
            args.extend(["--min-qty", str(min_qty)])
    elif mode == "pct_of_equity":
        args.extend(["--sizing", "pct_of_equity", "--equity", f"{equity_value:.2f}"])
        pos_pct = sizing_cfg.get("pos_pct")
        if pos_pct is not None:
            args.extend(["--pos-pct", str(pos_pct)])
    elif mode == "fixed":
        args.extend(["--sizing", "fixed"])
        qty = sizing_cfg.get("qty")
        if qty is not None:
            args.extend(["--qty", str(qty)])
    return args


def run_backtest(
    config_path: Optional[str],
    run_name: str,
    config_payload: Optional[dict] = None,
    log_title: Optional[str] = None,
) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    if config_payload is not None:
        tmp_file = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8")
        with tmp_file as handle:
            yaml.safe_dump(config_payload, handle)
        config_path = tmp_file.name

    if not config_path:
        raise ValueError("Configuration path is required")

    path_obj = Path(config_path)
    if not path_obj.is_absolute():
        path_obj = (ROOT / path_obj).resolve()
    config_path = str(path_obj)

    cmd = [
        sys.executable,
        "-m",
        "axiom_bt.runner",
        "--config",
        config_path,
        "--name",
        run_name,
    ]
    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    duration = time.perf_counter() - start
    output = _combine_output(result.stdout, result.stderr)
    if log_title:
        _set_last_duration(duration)
        show_step(log_title, cmd, result.returncode, output)
    elif result.returncode != 0:
        st.error(output or "Runner failed")
        raise RuntimeError("Backtest failed")

    runs = [d for d in BT_DIR.glob("run_*") if d.is_dir()]
    runs.sort(key=lambda directory: directory.stat().st_mtime, reverse=True)
    return runs[0].name if runs else run_name




from datetime import datetime, timezone


def execute_pipeline(pipeline: PipelineConfig) -> str:
    """Execute a full pipeline run from the UI.

    This function always produces a run_log.json under
    artifacts/backtests/<ui_run_name>/ regardless of whether Stage 2
    runs, so that every UI-triggered run has a clear status and trace.
    """

    # Reset in-memory log buffer at the very beginning so this run
    # has a clean, complete trace from the first event.
    global _LOG_ENTRIES
    _LOG_ENTRIES = []

    run_name = pipeline.run_name
    run_dir = BT_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    run_started_at = datetime.now(timezone.utc).isoformat()
    _store_log({
        "kind": "run_meta",
        "phase": "start",
        "run_name": run_name,
        "strategy": pipeline.strategy.strategy_name,
        "symbols": list(pipeline.symbols),
        "timeframe": pipeline.fetch.timeframe,
        "started_at": run_started_at,
    })

    final_status = "unknown"

    try:
        # --- Two-Stage Pipeline (Capability + Hook-Based, e.g. Rudometkin) ---
        if pipeline.strategy.supports_two_stage_pipeline:
            # Lazy-import the strategy-specific pipeline module so it can
            # register its hooks with strategy_hooks. This keeps the central
            # pipeline generic while allowing strategies to extend behavior.
            try:
                __import__(f"strategies.{pipeline.strategy.strategy_name}.pipeline")
            except ImportError as exc:
                show_step_message(
                    "0) Daily Scan",
                    "Failed to import pipeline module for "
                    f"'{pipeline.strategy.strategy_name}': {type(exc).__name__}: {exc}",
                    status="error",
                )
                final_status = "error_import_daily_scan_module"
                return "No Candidates"

            daily_scan = strategy_hooks.get_daily_scan(pipeline.strategy.strategy_name)
            if daily_scan is None:
                show_step_message(
                    "0) Daily Scan",
                    f"No daily_scan hook registered for strategy '{pipeline.strategy.strategy_name}'.",
                    status="error",
                )
                final_status = "error_no_daily_scan_hook"
                return "No Candidates"

            max_daily = 10
            if pipeline.config_payload and "max_daily_signals" in pipeline.config_payload:
                try:
                    max_daily = int(pipeline.config_payload["max_daily_signals"])
                except (TypeError, ValueError):
                    pass

            filtered_symbols = daily_scan(pipeline, max_daily)

            # Log outcome of daily scan so RK runs have a visible step in
            # run_log.json, then narrow the pipeline for Stage 2. Only
            # abort early when there are truly no candidates.
            if not filtered_symbols:
                show_step_message(
                    "Stage 2 Aborted",
                    "No candidates found after filtering.",
                    status="warning",
                )
                _store_log({
                    "kind": "step",
                    "title": "0) Daily Scan (Rudometkin)",
                    "status": "warning_no_candidates",
                    "details": "No candidates after daily filtering",
                })
                final_status = "warning_no_candidates"
                return "No Candidates"

            # Defensive guard: for two-stage strategies like Rudometkin we
            # expect a small, bounded candidate set per day (max_daily long
            # + max_daily short). If the returned candidate set is
            # unreasonably large compared to the requested window, treat it
            # as a pipeline error rather than attempting a full-universe
            # intraday fetch.
            days_in_window = None
            if pipeline.fetch.start and pipeline.fetch.end:
                try:
                    start_date = pd.Timestamp(pipeline.fetch.start).date()
                    end_date = pd.Timestamp(pipeline.fetch.end).date()
                    days_in_window = (end_date - start_date).days + 1
                except Exception:
                    days_in_window = None
            # Fallback: if dates are missing or invalid, assume a very small
            # window so the guard still triggers for obviously bad cases.
            if not days_in_window or days_in_window <= 0:
                days_in_window = 3

            expected_max = days_in_window * max_daily * 2
            hard_cap = expected_max * 5
            if len(filtered_symbols) > hard_cap:
                message = (
                    f"Daily scan returned {len(filtered_symbols)} symbols for a window of "
                    f"{days_in_window} days with max_daily_signals={max_daily}. "
                    "This exceeds the safety cap and would trigger a full-universe "
                    "intraday fetch, so Stage 2 is aborted."
                )
                show_step_message(
                    "0) Daily Scan (Rudometkin)",
                    message,
                    status="error",
                )
                _store_log({
                    "kind": "step",
                    "title": "0) Daily Scan (Rudometkin)",
                    "status": "error_unreasonable_candidate_count",
                    "details": message,
                })
                final_status = "error_unreasonable_candidate_count"
                return "No Candidates"

            _store_log({
                "kind": "step",
                "title": "0) Daily Scan (Rudometkin)",
                "status": "success",
                "details": f"{len(filtered_symbols)} unique symbols after daily filtering",
            })

            # Rebuild pipeline so that Stage 2 (intraday + backtest) only
            # operates on the filtered candidate symbols.
            pipeline = PipelineConfig(
                run_name=pipeline.run_name,
                fetch=FetchConfig(
                    symbols=filtered_symbols,
                    timeframe=pipeline.fetch.timeframe,
                    start=pipeline.fetch.start,
                    end=pipeline.fetch.end,
                    use_sample=pipeline.fetch.use_sample,
                    force_refresh=pipeline.fetch.force_refresh,
                    data_dir=pipeline.fetch.data_dir,
                    data_dir_m1=pipeline.fetch.data_dir_m1,
                ),
                symbols=filtered_symbols,
                strategy=pipeline.strategy,
                config_path=pipeline.config_path,
                config_payload=pipeline.config_payload,
            )

        # --- Standard Pipeline (Intraday) ---
        # For two-stage strategies (e.g. Rudometkin) we expect Stage 1 to have
        # rebuilt the pipeline so that both `pipeline.symbols` and
        # `pipeline.fetch.symbols` are the narrowed candidate set.
        if pipeline.strategy.supports_two_stage_pipeline:
            if set(pipeline.symbols) != set(pipeline.fetch.symbols):  # pragma: no cover - defensive
                show_step_message(
                    "0) configuration error",
                    "Two-stage pipeline inconsistency: symbols and fetch.symbols differ; "
                    "aborting intraday stage to avoid full-universe fetch.",
                    status="error",
                )
                final_status = "error_two_stage_mismatch"
                return "No Candidates"

        fetch_targets = pipeline.fetch.symbols_to_fetch()
        reasons = pipeline.fetch.stale_reasons()
        if fetch_targets:
            fetch_args = [
                "axiom_bt.cli_data",
                "ensure-intraday",
                "--symbols",
                ",".join(fetch_targets),
                "--tz",
                "America/New_York",
            ]
            if pipeline.fetch.start:
                fetch_args.extend(["--start", pipeline.fetch.start])
            if pipeline.fetch.end:
                fetch_args.extend(["--end", pipeline.fetch.end])
            if pipeline.fetch.force_refresh or pipeline.fetch.needs_force_refresh():
                fetch_args.append("--force")
            if pipeline.fetch.timeframe.upper() == "M15":
                fetch_args.append("--generate-m15")
            if pipeline.fetch.use_sample:
                fetch_args.append("--use-sample")
            if reasons and not pipeline.fetch.force_refresh:
                messages = []
                for symbol, entries in reasons.items():
                    joined = "; ".join(entries)
                    messages.append(f"{symbol}: {joined}")
                if messages:
                    show_step_message("0) data coverage", "\n".join(messages), status="warning")
            run_cli_step("0) ensure-intraday", fetch_args)
            st.cache_data.clear()
        else:
            show_step_message("0) ensure-intraday", "Skipped (cached data)")

        signal_args = [
            pipeline.strategy.signal_module,
            "--symbols",
            ",".join(pipeline.symbols),
            "--data-path",
            str(pipeline.fetch.data_dir),
        ]
        signal_args.extend(["--tz", pipeline.strategy.timezone])
        signal_args.extend(["--strategy", pipeline.strategy.strategy_name])
        signal_args.extend(["--current-snapshot", str(pipeline.strategy.orders_source)])
        strategy_config: Dict[str, Any] = {}
        if pipeline.config_payload and isinstance(pipeline.config_payload, dict):
            strategy_config = pipeline.config_payload.get("strategy_config", {}) or {}
        if not strategy_config and pipeline.strategy.default_strategy_config:
            strategy_config = dict(pipeline.strategy.default_strategy_config)
        universe_path = strategy_config.get("universe_path")
        if universe_path:
            signal_args.extend(["--universe-path", str(universe_path)])

        run_cli_step(f"1) {pipeline.strategy.signal_module}", signal_args)

        equity_value = _resolve_initial_cash(pipeline)
        risk_pct_override = None
        if pipeline.config_payload and "risk_pct" in pipeline.config_payload:
            try:
                risk_pct_override = float(pipeline.config_payload["risk_pct"])
            except (TypeError, ValueError):
                risk_pct_override = None

        orders_args = [
            "trade.cli_export_orders",
            "--source",
            str(pipeline.strategy.orders_source),
            "--sessions",
            ",".join(pipeline.strategy.sessions),
            "--tz",
            pipeline.strategy.timezone,
        ]
        orders_args.extend(_build_sizing_args(pipeline, equity_value, risk_pct_override))
        orders_args.extend(["--strategy", pipeline.strategy.strategy_name])
        run_cli_step("2) trade.cli_export_orders", orders_args)

        if pipeline.config_payload is not None:
            data_cfg = pipeline.config_payload.setdefault("data", {})
            data_cfg.setdefault("path", str(pipeline.fetch.data_dir))
            data_cfg.setdefault("path_m1", str(pipeline.fetch.data_dir_m1))

        run_name_from_runner = run_backtest(
            pipeline.config_path,
            pipeline.run_name,
            pipeline.config_payload,
            log_title="3) axiom_bt.runner",
        )

        # If runner returned a canonical run_* directory, prefer that as
        # the effective run identifier for downstream inspection.
        effective_run_name = run_name_from_runner or run_name
        final_status = "success"
        return effective_run_name

    except Exception as exc:  # pragma: no cover - pipeline-level failure
        _store_log({
            "kind": "error",
            "title": "Pipeline Exception",
            "message": f"{type(exc).__name__}: {exc}",
            "status": "error",
        })
        final_status = "error"
        raise

    finally:
        # Persist structured run log for ANY outcome under the UI run name
        # directory so every run has a trace and status.
        try:
            run_finished_at = datetime.now(timezone.utc).isoformat()
            _store_log({
                "kind": "run_meta",
                "phase": "end",
                "run_name": run_name,
                "strategy": pipeline.strategy.strategy_name,
                "symbols": list(pipeline.symbols),
                "timeframe": pipeline.fetch.timeframe,
                "finished_at": run_finished_at,
                "status": final_status,
            })

            log_path = run_dir / "run_log.json"
            log_payload = {
                "run_name": run_name,
                "strategy": pipeline.strategy.strategy_name,
                "symbols": list(pipeline.symbols),
                "timeframe": pipeline.fetch.timeframe,
                "created_at": run_started_at,
                "finished_at": run_finished_at,
                "status": final_status,
                "entries": get_pipeline_log(),
            }
            log_path.write_text(json.dumps(log_payload, indent=2), encoding="utf-8")
        except Exception:  # pragma: no cover - best-effort logging
            pass
