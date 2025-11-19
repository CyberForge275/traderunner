from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))
os.environ.setdefault("PYTHONPATH", str(SRC))

BT_DIR = ROOT / "artifacts" / "backtests"

from core.settings import DEFAULT_INITIAL_CASH
from state import PipelineConfig


def _format_command(cmd: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def _combine_output(stdout: str | None, stderr: str | None) -> str:
    parts = []
    if stdout:
        parts.append(stdout.strip())
    if stderr:
        parts.append(stderr.strip())
    return "\n".join(part for part in parts if part)


def show_step(title: str, cmd: List[str], rc: int, output: str) -> None:
    with st.expander(title, expanded=True):
        st.code(_format_command(cmd) or "(no command)")
        if rc == 0:
            st.success("OK")
        else:
            st.error(f"[ERROR] rc={rc}")
        if output:
            st.text(output)
    if rc != 0:
        raise RuntimeError(title)


def show_step_message(title: str, message: str, status: str = "info") -> None:
    with st.expander(title, expanded=True):
        st.code("(skipped)")
        display = getattr(st, status, st.info)
        display(message)


def run_cli_step(title: str, module_args: List[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    cmd = [sys.executable, "-m", *module_args]
    result = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    output = _combine_output(result.stdout, result.stderr)
    show_step(title, cmd, result.returncode, output)
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
        except Exception:
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
    result = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    output = _combine_output(result.stdout, result.stderr)
    if log_title:
        show_step(log_title, cmd, result.returncode, output)
    elif result.returncode != 0:
        st.error(output or "Runner failed")
        raise RuntimeError("Backtest failed")

    runs = [d for d in BT_DIR.glob("run_*") if d.is_dir()]
    runs.sort(key=lambda directory: directory.stat().st_mtime, reverse=True)
    return runs[0].name if runs else run_name


def execute_pipeline(pipeline: PipelineConfig) -> str:
    fetch_targets = pipeline.fetch.symbols_to_fetch()
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
    run_cli_step("1) signals.cli_inside_bar", signal_args)

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
    run_cli_step("2) trade.cli_export_orders", orders_args)

    if pipeline.config_payload is not None:
        data_cfg = pipeline.config_payload.setdefault("data", {})
        data_cfg.setdefault("path", str(pipeline.fetch.data_dir))
        data_cfg.setdefault("path_m1", str(pipeline.fetch.data_dir_m1))

    return run_backtest(pipeline.config_path, pipeline.run_name, pipeline.config_payload, log_title="3) axiom_bt.runner")
