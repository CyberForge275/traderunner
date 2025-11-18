from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
BT_DIR = ROOT / "artifacts" / "backtests"
os.environ.setdefault("PYTHONPATH", str(SRC))

DATA_DIRECTORIES = {
    "M5": ROOT / "artifacts" / "data_m5",
    "M15": ROOT / "artifacts" / "data_m15",
}


@st.cache_data(show_spinner=False)
def list_runs(base_dir: str) -> list[str]:
    base = Path(base_dir)
    runs = [d for d in base.glob("run_*") if d.is_dir()]
    runs.sort(key=lambda directory: directory.stat().st_mtime, reverse=True)
    return [d.name for d in runs]


@st.cache_data(show_spinner=False)
def list_symbols(data_dir: str) -> list[str]:
    path = Path(data_dir)
    if not path.exists():
        return []
    return sorted({p.stem.upper() for p in path.glob("*.parquet")})


def _format_command(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def _combine_output(stdout: str | None, stderr: str | None) -> str:
    parts = []
    if stdout:
        parts.append(stdout.strip())
    if stderr:
        parts.append(stderr.strip())
    return "\n".join(part for part in parts if part)


def show_step(title: str, cmd: list[str], rc: int, output: str) -> None:
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


def run_cli_step(title: str, module_args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    cmd = [sys.executable, "-m", *module_args]
    result = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    output = _combine_output(result.stdout, result.stderr)
    show_step(title, cmd, result.returncode, output)
    return result


def run_backtest(
    config_path: str | None,
    run_name: str,
    config_payload: dict | None = None,
    log_title: str | None = None,
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


def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def _read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def load_run(run_name: str) -> dict:
    run_dir = BT_DIR / run_name
    return {
        "run_dir": run_dir,
        "metrics": _read_json(run_dir / "metrics.json"),
        "equity_png": run_dir / "equity_curve.png",
        "dd_png": run_dir / "drawdown_curve.png",
        "equity_csv": _read_csv(run_dir / "equity_curve.csv"),
        "fills_csv": _read_csv(run_dir / "filled_orders.csv"),
        "trades_csv": _read_csv(run_dir / "trades.csv"),
        "manifest": _read_json(run_dir / "manifest.json"),
    }


st.set_page_config(page_title="TradeRunner Backtest Dashboard", layout="wide")

selected_run: str | None = None

with st.sidebar:
    st.header("Run configuration")
    timeframe = st.selectbox("Timeframe", tuple(DATA_DIRECTORIES.keys()), index=0)
    data_directory = DATA_DIRECTORIES[timeframe]
    cached_symbols = list_symbols(str(data_directory))
    default_cached = cached_symbols[:1]
    cached_selection = st.multiselect(
        "Cached symbols",
        cached_symbols,
        default=default_cached,
        help="Symbols already available as parquet files for the selected timeframe.",
    )

    st.caption("Compose the symbol list for this run")
    symbol_input = st.text_area(
        "Symbols to process",
        value="",
        height=80,
        placeholder="Enter comma or newline separated tickers (e.g. TSLA, AAPL, NVDA)",
    ).strip()
    use_sample = st.checkbox("Use synthetic data when fetching", value=False)
    force_refresh = st.checkbox("Force refresh data", value=False)

    run_name_key = "run_name_input"
    run_name_scope_key = "run_name_scope"
    generated_default = f"ui_{timeframe.lower()}_{int(pd.Timestamp.utcnow().timestamp())}"

    if run_name_key not in st.session_state:
        st.session_state[run_name_key] = generated_default
        st.session_state[run_name_scope_key] = timeframe
    elif st.session_state.get(run_name_scope_key) != timeframe:
        st.session_state[run_name_key] = generated_default
        st.session_state[run_name_scope_key] = timeframe

    run_name = st.text_input("Run name", value=st.session_state[run_name_key], key=run_name_key)

    with st.expander("Strategy & backtest parameters", expanded=True):
        config_mode = st.radio(
            "Configuration source",
            ("Use YAML file", "Manual"),
            index=0,
        )

        config_payload = None
        config_path_for_run: str | None = None
        fetch_start_str: str | None = None
        fetch_end_str: str | None = None

        if config_mode == "Use YAML file":
            yaml_input = st.text_input("YAML config", "configs/runs/insidebar.yml")
            if yaml_input:
                config_path = Path(yaml_input.strip())
                if not config_path.is_absolute():
                    config_path = (ROOT / config_path).resolve()
                if config_path.exists():
                    config_path_for_run = str(config_path)
                    try:
                        yaml_payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                    except Exception as exc:
                        st.warning(f"Could not parse YAML: {exc}")
                        yaml_payload = None
                    if isinstance(yaml_payload, dict) and yaml_payload:
                        options = ["(Show all)"] + list(yaml_payload.keys())
                        choice = st.selectbox(
                            "Inspect YAML parameters",
                            options,
                            index=0,
                            key="yaml_param_select",
                        )
                        if choice == "(Show all)":
                            st.json(yaml_payload)
                        else:
                            st.json({choice: yaml_payload.get(choice)})
                    elif yaml_payload is not None:
                        st.json(yaml_payload)
                else:
                    st.warning(f"Config file not found: {config_path}")
                    config_path_for_run = str(config_path)
        else:
            st.caption("Override core replay parameters directly.")
            orders_csv = st.text_input(
                "Orders CSV",
                str(ROOT / "artifacts/orders/current_orders.csv"),
            )
            data_path = st.text_input(
                "Data directory",
                str(data_directory),
            )
            tz_value = st.text_input("Timezone", "America/New_York")
            fees_bps = st.number_input("Fees (bps)", value=2.0, step=0.1)
            slippage_bps = st.number_input("Slippage (bps)", value=1.0, step=0.1)
            initial_cash = st.number_input("Initial cash", value=100_000.0, step=1_000.0)
            mode_value = st.selectbox("Strategy mode", ["insidebar_intraday"], index=0)

            date_mode = st.radio(
                "Date selection",
                ("Days back from anchor", "Explicit date range"),
                index=0,
                key="manual_date_mode",
            )
            today = pd.Timestamp.today().date()

            if date_mode == "Days back from anchor":
                anchor_date = st.date_input(
                    "Anchor date",
                    value=today,
                    key="manual_anchor_date",
                )
                days_back = st.number_input(
                    "Days back",
                    min_value=1,
                    value=30,
                    step=1,
                    key="manual_days_back",
                )
                if isinstance(anchor_date, tuple):
                    anchor_date = anchor_date[0]
                anchor_ts = pd.Timestamp(anchor_date)
                start_ts = anchor_ts - pd.Timedelta(days=int(days_back))
                fetch_start_str = start_ts.date().isoformat()
                fetch_end_str = anchor_ts.date().isoformat()
                st.caption(f"Data window: {fetch_start_str} → {fetch_end_str}")
            else:
                default_range = (
                    today - pd.Timedelta(days=30),
                    today,
                )
                selected_range = st.date_input(
                    "Date range",
                    value=default_range,
                    key="manual_date_range",
                )
                if isinstance(selected_range, tuple) and len(selected_range) == 2:
                    start_date = min(selected_range)
                    end_date = max(selected_range)
                else:
                    start_date = end_date = selected_range
                start_ts = pd.Timestamp(start_date)
                end_ts = pd.Timestamp(end_date)
                fetch_start_str = start_ts.date().isoformat()
                fetch_end_str = end_ts.date().isoformat()
                st.caption(f"Data window: {fetch_start_str} → {fetch_end_str}")

            config_payload = {
                "name": run_name,
                "engine": "replay",
                "mode": mode_value,
                "orders_source_csv": orders_csv,
                "data": {"path": data_path, "tz": tz_value},
                "costs": {"fees_bps": float(fees_bps), "slippage_bps": float(slippage_bps)},
                "initial_cash": float(initial_cash),
            }
            config_path_for_run = None

    if st.button("Start backtest", type="primary", width="stretch"):
        try:
            parsed_symbols = set(sym.upper() for sym in cached_selection if sym)
            if symbol_input:
                parts = [p.strip().upper() for p in symbol_input.replace("\n", ",").split(",") if p.strip()]
                parsed_symbols.update(parts)

            symbol_set = sorted(parsed_symbols)
            if not symbol_set:
                st.error("Select or enter at least one symbol.")
                st.stop()

            if config_mode == "Use YAML file" and not config_path_for_run:
                st.error("Provide a valid YAML config path.")
                st.stop()

            symbols_to_fetch = symbol_set
            if not force_refresh:
                symbols_to_fetch = [
                    sym
                    for sym in symbol_set
                    if not (data_directory / f"{sym}.parquet").exists()
                ]

            fetch_targets = symbol_set if force_refresh else symbols_to_fetch
            if fetch_targets:
                fetch_args = [
                    "axiom_bt.cli_data",
                    "ensure-intraday",
                    "--symbols",
                    ",".join(fetch_targets),
                    "--tz",
                    "America/New_York",
                ]
                if fetch_start_str:
                    fetch_args.extend(["--start", fetch_start_str])
                if fetch_end_str:
                    fetch_args.extend(["--end", fetch_end_str])
                if force_refresh:
                    fetch_args.append("--force")
                if timeframe.upper() == "M15":
                    fetch_args.append("--generate-m15")
                if use_sample:
                    fetch_args.append("--use-sample")
                run_cli_step("0) ensure-intraday", fetch_args)
                st.cache_data.clear()
            else:
                show_step_message("0) ensure-intraday", "Skipped (cached data)")

            signal_args = [
                "signals.cli_inside_bar",
                "--symbols",
                ",".join(symbol_set),
                "--data-path",
                str(data_directory),
            ]
            run_cli_step("1) signals.cli_inside_bar", signal_args)

            orders_args = [
                "trade.cli_export_orders",
                "--source",
                str(ROOT / "artifacts" / "signals" / "current_signals_ib.csv"),
                "--sessions",
                "15:00-16:00,16:00-17:00",
                "--tz",
                "Europe/Berlin",
            ]
            run_cli_step("2) trade.cli_export_orders", orders_args)

            new_run = run_backtest(config_path_for_run, run_name, config_payload, log_title="3) axiom_bt.runner")
            finished_at = pd.Timestamp.now(tz="Europe/Berlin").isoformat()
            st.success(f"Run finished → {new_run} at {finished_at}")
            st.session_state[run_name_key] = f"ui_{timeframe.lower()}_{int(pd.Timestamp.utcnow().timestamp())}"
            st.session_state[run_name_scope_key] = timeframe
            st.cache_data.clear()
            st.session_state["selected_run"] = new_run
            st.experimental_rerun()
        except Exception:
            st.stop()

    st.markdown("---")
    st.subheader("Past runs")
    if st.button("Refresh list", width="stretch"):
        st.cache_data.clear()

    runs = list_runs(str(BT_DIR))
    if not runs:
        st.info("No runs available yet.")
        st.session_state.pop("selected_run", None)
        selected_run = None
    else:
        selected_default = st.session_state.get("selected_run", runs[0])
        try:
            index = runs.index(selected_default)
        except ValueError:
            index = 0
        selected_run = st.selectbox("Select run", runs, index=index)
        st.session_state["selected_run"] = selected_run


if not selected_run:
    st.info("Run outputs will appear here after you execute a backtest.")
    st.stop()

run = load_run(selected_run)
st.caption(f"Displaying results for run: `{selected_run}`")
columns = st.columns([1, 1])

with columns[0]:
    st.subheader("Metrics")
    metrics = run["metrics"] or {}
    if metrics:
        st.json(metrics)
    else:
        st.info("No metrics available for this run yet.")

with columns[0]:
    st.subheader("Equity curve")
    if run["equity_png"].exists():
        st.image(str(run["equity_png"]), width="stretch")
    elif run["equity_csv"] is not None and not run["equity_csv"].empty:
        try:
            chart_df = run["equity_csv"].copy()
            chart_df["ts"] = pd.to_datetime(chart_df["ts"], errors="coerce")
            chart_df = chart_df.dropna(subset=["ts"]).set_index("ts")
            st.line_chart(chart_df["equity"])
        except Exception:
            st.info("Equity data could not be plotted.")
    else:
        st.info("No equity data found.")

with columns[1]:
    st.subheader("Drawdown (pct)")
    if run["dd_png"].exists():
        st.image(str(run["dd_png"]), width="stretch")
    elif run["equity_csv"] is not None and "drawdown_pct" in run["equity_csv"].columns:
        try:
            chart_df = run["equity_csv"].copy()
            chart_df["ts"] = pd.to_datetime(chart_df["ts"], errors="coerce")
            chart_df = chart_df.dropna(subset=["ts"]).set_index("ts")
            st.line_chart(chart_df["drawdown_pct"])
        except Exception:
            st.info("Drawdown data could not be plotted.")
    else:
        st.info("No drawdown plot found.")


tabs = st.tabs(["filled_orders.csv", "trades.csv"])
with tabs[0]:
    filled_df = run["fills_csv"]
    if filled_df is not None and not filled_df.empty:
        st.dataframe(filled_df, width="stretch", height=360)
    else:
        st.info("No fills available.")

with tabs[1]:
    trades_df = run["trades_csv"]
    if trades_df is not None and not trades_df.empty:
        st.dataframe(trades_df, width="stretch", height=360)
    else:
        st.info("No trades available.")
