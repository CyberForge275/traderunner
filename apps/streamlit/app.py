from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

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


SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._-]+$")


def collect_symbols(selection: Iterable[str], free_text: str) -> Tuple[List[str], List[str]]:
    """Normalize and validate symbol inputs."""
    symbols = {sym.strip().upper() for sym in selection if sym}
    if free_text:
        tokens = [token.strip().upper() for token in free_text.replace("\n", ",").split(",") if token.strip()]
        symbols.update(tokens)

    errors: List[str] = []
    invalid = sorted(sym for sym in symbols if not SYMBOL_PATTERN.fullmatch(sym))
    if invalid:
        errors.append(f"Invalid symbol format: {', '.join(invalid)}")
    valid_symbols = sorted(sym for sym in symbols if sym not in invalid)
    if not valid_symbols:
        errors.append("Select or enter at least one valid symbol.")
    return valid_symbols, errors


def validate_date_range(start: Optional[str], end: Optional[str]) -> List[str]:
    errors: List[str] = []
    if start and end:
        try:
            start_ts = pd.Timestamp(start)
            end_ts = pd.Timestamp(end)
            if start_ts > end_ts:
                errors.append(f"Date range invalid: start {start} is after end {end}.")
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Invalid date range ({start} → {end}): {exc}")
    return errors


def parse_yaml_config(path_str: str) -> Tuple[Optional[str], Optional[Dict], List[str]]:
    errors: List[str] = []
    payload: Optional[Dict] = None
    if not path_str:
        errors.append("Provide a YAML config path.")
        return None, None, errors

    path = Path(path_str)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        errors.append(f"Config file not found: {path}")
        return str(path), None, errors

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.append(f"Failed to parse YAML: {exc}")
        return str(path), None, errors

    if not isinstance(raw, dict):
        errors.append("YAML root must be a mapping of parameters.")
    else:
        payload = raw

    return str(path), payload, errors


def _timestamp_to_date(ts: pd.Timestamp) -> pd.Timestamp.date:
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC")
    return ts.date()


def _index_date_bounds(index: pd.DatetimeIndex) -> Tuple[pd.Timestamp.date, pd.Timestamp.date]:
    return _timestamp_to_date(index.min()), _timestamp_to_date(index.max())


@dataclass
class FetchConfig:
    symbols: List[str]
    timeframe: str
    start: Optional[str]
    end: Optional[str]
    use_sample: bool
    force_refresh: bool
    data_dir: Path

    def symbols_to_fetch(self) -> List[str]:
        if self.force_refresh:
            return list(self.symbols)
        missing = [sym for sym in self.symbols if not self._has_coverage(sym)]
        return missing

    def _has_coverage(self, symbol: str) -> bool:
        path = self.data_dir / f"{symbol}.parquet"
        if not path.exists():
            return False
        if not self.start and not self.end:
            return True
        try:
            index = pd.read_parquet(path, columns=["Close"]).index
        except Exception:
            return False
        if index.empty:
            return False

        min_date, max_date = _index_date_bounds(index)
        if self.start:
            start_date = pd.Timestamp(self.start).date()
            if min_date > start_date:
                return False
        if self.end:
            end_date = pd.Timestamp(self.end).date()
            if max_date < end_date:
                return False
        return True


@dataclass
class StrategyMetadata:
    name: str
    label: str
    timezone: str
    sessions: List[str]
    signal_module: str
    orders_source: Path
    default_payload: Dict


INSIDE_BAR_METADATA = StrategyMetadata(
    name="insidebar_intraday",
    label="Inside Bar Intraday",
    timezone="Europe/Berlin",
    sessions=["15:00-16:00", "16:00-17:00"],
    signal_module="signals.cli_inside_bar",
    orders_source=ROOT / "artifacts" / "signals" / "current_signals_ib.csv",
    default_payload={
        "engine": "replay",
        "mode": "insidebar_intraday",
        "data": {"tz": "Europe/Berlin"},
        "costs": {"fees_bps": 2.0, "slippage_bps": 1.0},
        "initial_cash": 100_000.0,
    },
)


STRATEGY_REGISTRY: Dict[str, StrategyMetadata] = {
    INSIDE_BAR_METADATA.name: INSIDE_BAR_METADATA,
}


@dataclass
class PipelineConfig:
    run_name: str
    fetch: FetchConfig
    symbols: List[str]
    strategy: StrategyMetadata
    config_path: Optional[str]
    config_payload: Optional[Dict]


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
        if pipeline.fetch.force_refresh:
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
    run_cli_step("1) signals.cli_inside_bar", signal_args)

    orders_args = [
        "trade.cli_export_orders",
        "--source",
        str(pipeline.strategy.orders_source),
        "--sessions",
        ",".join(pipeline.strategy.sessions),
        "--tz",
        pipeline.strategy.timezone,
    ]
    run_cli_step("2) trade.cli_export_orders", orders_args)

    return run_backtest(pipeline.config_path, pipeline.run_name, pipeline.config_payload, log_title="3) axiom_bt.runner")


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
    cached_selection = st.multiselect(
        "Select cached symbols for this run",
        cached_symbols,
        help="Symbols already downloaded; select the ones you want to include in this run.",
    )
    if cached_symbols:
        unused_cached = sorted(set(cached_symbols) - set(cached_selection))
        st.caption(
            "Cached (not selected): " + (", ".join(unused_cached) if unused_cached else "—")
        )

    st.caption("Compose the symbol list for this run")
    symbol_input = st.text_area(
        "Symbols to process",
        value="",
        height=80,
        placeholder="Enter comma or newline separated tickers (e.g. TSLA, AAPL, NVDA)",
    ).strip()
    symbol_preview, symbol_preview_errors = collect_symbols(cached_selection, symbol_input)
    if symbol_preview:
        st.markdown(
            "**Symbols queued for this run:** " + ", ".join(symbol_preview)
        )
    else:
        st.info("No symbols selected yet.")
    for msg in symbol_preview_errors:
        st.warning(msg)
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
            ("Manual", "Use YAML file"),
            index=0,
        )

        config_payload = None
        config_path_for_run: str | None = None
        fetch_start_str: str | None = None
        fetch_end_str: str | None = None

        yaml_preview_errors: List[str] = []
        manual_date_errors: List[str] = []

        if config_mode == "Use YAML file":
            yaml_input = st.text_input("YAML config", "configs/runs/insidebar.yml")
            if yaml_input:
                config_path_for_run, yaml_payload, yaml_preview_errors = parse_yaml_config(yaml_input)
                for msg in yaml_preview_errors:
                    st.warning(msg)
                if yaml_payload:
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
            tz_value = st.text_input("Timezone", INSIDE_BAR_METADATA.timezone)
            fees_bps = st.number_input("Fees (bps)", value=float(INSIDE_BAR_METADATA.default_payload["costs"]["fees_bps"]), step=0.1)
            slippage_bps = st.number_input("Slippage (bps)", value=float(INSIDE_BAR_METADATA.default_payload["costs"]["slippage_bps"]), step=0.1)
            initial_cash = st.number_input("Initial cash", value=float(INSIDE_BAR_METADATA.default_payload["initial_cash"]), step=1_000.0)
            mode_value = st.selectbox(
                "Strategy mode",
                list(STRATEGY_REGISTRY.keys()),
                index=0,
                format_func=lambda key: STRATEGY_REGISTRY[key].label,
            )

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
            manual_date_errors = validate_date_range(fetch_start_str, fetch_end_str)
            for msg in manual_date_errors:
                st.warning(msg)

            config_payload = {
                "name": run_name,
                **STRATEGY_REGISTRY[mode_value].default_payload,
                "mode": mode_value,
                "orders_source_csv": orders_csv,
                "data": {
                    "path": data_path,
                    "tz": tz_value,
                },
                "costs": {
                    "fees_bps": float(fees_bps),
                    "slippage_bps": float(slippage_bps),
                },
                "initial_cash": float(initial_cash),
            }
            config_path_for_run = None

    if st.button("Start backtest", type="primary", width="stretch"):
        try:
            validation_errors: List[str] = []

            symbol_set = symbol_preview
            validation_errors.extend(symbol_preview_errors)

            manual_mode = config_mode == "Manual"
            if not manual_mode:
                validation_errors.extend(yaml_preview_errors)
                if not config_path_for_run:
                    validation_errors.append("Provide a valid YAML config path.")
            else:
                validation_errors.extend(manual_date_errors)

            if validation_errors:
                for err in validation_errors:
                    st.error(err)
                st.stop()

            fetch_config = FetchConfig(
                symbols=symbol_set,
                timeframe=timeframe,
                start=fetch_start_str,
                end=fetch_end_str,
                use_sample=use_sample,
                force_refresh=force_refresh,
                data_dir=data_directory,
            )

            strategy_meta = STRATEGY_REGISTRY.get(mode_value, INSIDE_BAR_METADATA)

            pipeline = PipelineConfig(
                run_name=run_name,
                fetch=fetch_config,
                symbols=symbol_set,
                strategy=strategy_meta,
                config_path=config_path_for_run,
                config_payload=config_payload,
            )

            new_run = execute_pipeline(pipeline)
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
st.markdown(f"## Run: **{selected_run}**")
chart_columns = st.columns([1, 1])

with chart_columns[0]:
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

with chart_columns[1]:
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

metrics = run["metrics"] or {}
st.subheader("Metrics")
if metrics:
    metrics_items = sorted(metrics.items())
    metrics_df = pd.DataFrame(metrics_items, columns=["Metric", "Value"])
    st.table(metrics_df)
else:
    st.info("No metrics available for this run yet.")


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
