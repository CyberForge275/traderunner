from __future__ import annotations

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
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))
os.environ.setdefault("PYTHONPATH", str(SRC))

BT_DIR = ROOT / "artifacts" / "backtests"

from core.settings import DEFAULT_INITIAL_CASH
from state import FetchConfig, PipelineConfig
from strategies import factory, registry


def _store_log(entry: dict) -> None:
    try:
        log = st.session_state.setdefault("pipeline_log", [])
        log.append(entry)
    except Exception:  # pragma: no cover - defensive
        pass


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


def _prepare_daily_frame(group: pd.DataFrame, target_tz: str) -> Optional[pd.DataFrame]:
    frame = group.rename(columns=str.lower).copy()
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        return None
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"])
    if frame.empty:
        return None
    frame = frame.sort_values("timestamp")
    frame["timestamp"] = frame["timestamp"].dt.tz_convert(target_tz)
    return frame[["timestamp", "open", "high", "low", "close", "volume"]]


def _run_rudometkin_daily_stage(
    pipeline: PipelineConfig,
    max_daily_signals: int = 10,
) -> List[str]:
    """Execute daily scan and filtering for Rudometkin strategy."""

    show_step_message("0) Daily Scan", "Starting Stage 1: Daily Universe Scan & Filter")

    strategy_config: Dict[str, Any] = {}
    if pipeline.config_payload and isinstance(pipeline.config_payload, dict):
        strategy_config = dict(pipeline.config_payload.get("strategy_config", {}) or {})
    if not strategy_config and pipeline.strategy.default_strategy_config:
        strategy_config = dict(pipeline.strategy.default_strategy_config)

    universe_path = strategy_config.get("universe_path")
    if not universe_path:
        show_step_message(
            "0.1) universe",
            "Universe path not configured for Rudometkin strategy.",
            status="error",
        )
        return []

    universe_path = Path(universe_path)
    if not universe_path.is_absolute():
        universe_path = ROOT / universe_path

    if not universe_path.exists():
        show_step_message(
            "0.1) universe",
            f"Universe parquet not found: {universe_path}",
            status="error",
        )
        return []

    try:
        universe_df = pd.read_parquet(universe_path)
    except Exception as exc:  # pragma: no cover - defensive
        show_step_message(
            "0.1) universe",
            f"Failed to load universe parquet: {exc}",
            status="error",
        )
        return []

    if isinstance(universe_df.index, pd.MultiIndex):
        temp_symbol_col = "__symbol_index__"
        temp_date_col = "__date_index__"
        universe_df = universe_df.reset_index(names=[temp_symbol_col, temp_date_col])
        symbol_col = temp_symbol_col
        date_col = temp_date_col
    else:
        symbol_col = "symbol" if "symbol" in universe_df.columns else "Symbol"
        date_col = "Date" if "Date" in universe_df.columns else "timestamp"

    if symbol_col not in universe_df.columns or date_col not in universe_df.columns:
        show_step_message(
            "0.1) universe",
            "Universe parquet is missing symbol/date columns.",
            status="error",
        )
        return []

    universe_df = universe_df.rename(columns={symbol_col: "symbol", date_col: "timestamp"})
    universe_df["symbol"] = universe_df["symbol"].astype(str).str.upper()
    universe_df["timestamp"] = pd.to_datetime(universe_df["timestamp"], utc=True, errors="coerce")
    universe_df = universe_df.dropna(subset=["timestamp"])

    if universe_df.empty:
        show_step_message("0.1) universe", "Universe parquet is empty.", status="warning")
        return []

    if pipeline.fetch.start:
        start_date = pd.Timestamp(pipeline.fetch.start).date()
        universe_df = universe_df[universe_df["timestamp"].dt.date >= start_date]
    if pipeline.fetch.end:
        end_date = pd.Timestamp(pipeline.fetch.end).date()
        universe_df = universe_df[universe_df["timestamp"].dt.date <= end_date]

    requested_symbols = {sym.upper() for sym in pipeline.symbols} if pipeline.symbols else set()
    if requested_symbols:
        universe_df = universe_df[universe_df["symbol"].isin(requested_symbols)]

    available_symbols = set(universe_df["symbol"].unique())
    missing_symbols = sorted((requested_symbols or set()) - available_symbols)
    if missing_symbols:
        preview = ", ".join(missing_symbols[:20])
        suffix = " …" if len(missing_symbols) > 20 else ""
        show_step_message(
            "0.1) universe coverage",
            f"Missing daily data for {len(missing_symbols)} symbols: {preview}{suffix}",
            status="warning",
        )

    if universe_df.empty:
        show_step_message(
            "Stage 1 Aborted",
            "No daily data available after filtering universe.",
            status="warning",
        )
        return []

    registry.auto_discover("strategies")
    try:
        rudometkin_strategy = factory.create_strategy(pipeline.strategy.strategy_name, strategy_config)
    except Exception as exc:  # pragma: no cover - defensive
        show_step_message("0.2) strategy", f"Failed to load strategy: {exc}", status="error")
        return []

    signal_rows: List[Dict[str, Any]] = []
    for symbol, group in universe_df.groupby("symbol"):
        prepared = _prepare_daily_frame(group, pipeline.strategy.timezone)
        if prepared is None:
            continue
        try:
            signals = rudometkin_strategy.generate_signals(prepared, symbol, strategy_config)
        except Exception:  # pragma: no cover - defensive
            continue
        if not signals:
            continue
        for sig in signals:
            ts = pd.Timestamp(sig.timestamp)
            if ts.tzinfo is None:
                ts = ts.tz_localize(pipeline.strategy.timezone)
            else:
                ts = ts.tz_convert(pipeline.strategy.timezone)
            record = {
                "ts": ts.isoformat(),
                "Symbol": symbol,
                "long_entry": np.nan,
                "short_entry": np.nan,
                "sl_long": np.nan,
                "sl_short": np.nan,
                "tp_long": np.nan,
                "tp_short": np.nan,
                "setup": sig.metadata.get("setup"),
                "score": sig.metadata.get("score"),
            }
            direction = sig.signal_type.upper()
            if direction == "LONG":
                record["long_entry"] = sig.entry_price
            elif direction == "SHORT":
                record["short_entry"] = sig.entry_price
            signal_rows.append(record)

    columns = [
        "ts",
        "Symbol",
        "long_entry",
        "short_entry",
        "sl_long",
        "sl_short",
        "tp_long",
        "tp_short",
        "setup",
        "score",
    ]

    signals_df = pd.DataFrame(signal_rows, columns=columns)
    signals_dir = pipeline.strategy.orders_source.parent
    signals_dir.mkdir(parents=True, exist_ok=True)

    if signals_df.empty:
        empty_df = pd.DataFrame(columns=columns)
        timestamp_file = signals_dir / f"signals_rudometkin_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
        empty_df.to_csv(timestamp_file, index=False)
        empty_df.to_csv(pipeline.strategy.orders_source, index=False)
        show_step_message("0.3) Filter Signals", "No signals generated.", status="warning")
        return []

    signals_df["ts"] = pd.to_datetime(signals_df["ts"], errors="coerce")
    signals_df = signals_df.dropna(subset=["ts"])
    signals_df["score"] = pd.to_numeric(signals_df["score"], errors="coerce")
    signals_df["date"] = signals_df["ts"].dt.date

    filtered_chunks: List[pd.DataFrame] = []
    daily_details: List[str] = []

    for date, group in signals_df.groupby("date"):
        longs = group[group["long_entry"].notna()].sort_values("score", ascending=False).head(max_daily_signals)
        shorts = group[group["short_entry"].notna()].sort_values("score", ascending=False).head(max_daily_signals)

        long_syms = longs["Symbol"].tolist() if not longs.empty else []
        short_syms = shorts["Symbol"].tolist() if not shorts.empty else []

        if long_syms or short_syms:
            parts = []
            if long_syms:
                parts.append(f"LONG({len(long_syms)}): {', '.join(long_syms)}")
            if short_syms:
                parts.append(f"SHORT({len(short_syms)}): {', '.join(short_syms)}")
            daily_details.append(f"{date}: " + " | ".join(parts))

        if not longs.empty:
            filtered_chunks.append(longs)
        if not shorts.empty:
            filtered_chunks.append(shorts)

    if filtered_chunks:
        filtered_df = pd.concat(filtered_chunks).sort_values(["ts", "Symbol"]).drop(columns=["date"])
    else:
        filtered_df = pd.DataFrame(columns=columns)

    timestamp_file = signals_dir / f"signals_rudometkin_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filtered_df.to_csv(timestamp_file, index=False)
    filtered_df.to_csv(pipeline.strategy.orders_source, index=False)

    if filtered_df.empty:
        show_step_message("0.3) Filter Signals", "No signals generated after filtering.", status="warning")
        return []

    filtered_symbols = sorted(filtered_df["Symbol"].unique())
    summary_msg = (
        f"Filtered to {len(filtered_df)} signals ({len(filtered_symbols)} unique symbols). "
        f"Max/day={max_daily_signals}\n\n"
    )
    if daily_details:
        summary_msg += "Daily Candidates:\n" + "\n".join(daily_details)
    else:
        summary_msg += "No day produced qualifying candidates."
    show_step_message("0.3) Filter Signals", summary_msg)

    return filtered_symbols

def execute_pipeline(pipeline: PipelineConfig) -> str:
    # --- Two-Stage Pipeline for Rudometkin ---
    if pipeline.strategy.strategy_name == "rudometkin_moc":
        max_daily = 10
        if pipeline.config_payload and "max_daily_signals" in pipeline.config_payload:
            try:
                max_daily = int(pipeline.config_payload["max_daily_signals"])
            except (TypeError, ValueError):
                pass
        
        filtered_symbols = _run_rudometkin_daily_stage(pipeline, max_daily)
        
        if filtered_symbols:
            # Update symbols for intraday stage (creates a new list, no mutation)
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
        else:
            show_step_message("Stage 2 Aborted", "No candidates found after filtering.", status="warning")
            return "No Candidates"

    # --- Standard Pipeline (Intraday) ---
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

    return run_backtest(pipeline.config_path, pipeline.run_name, pipeline.config_payload, log_title="3) axiom_bt.runner")
