from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))
os.environ.setdefault("PYTHONPATH", str(SRC))

from core.settings import DEFAULT_INITIAL_CASH, INSIDE_BAR_TIMEZONE

from state import (
    FetchConfig,
    PipelineConfig,
    STRATEGY_REGISTRY,
    collect_symbols,
    parse_yaml_config,
    validate_date_range,
    INSIDE_BAR_METADATA,
    RUDOMETKIN_METADATA,
    RUDOMETKIN_UNIVERSE_DEFAULT,
)
from pipeline import execute_pipeline

BT_DIR = ROOT / "artifacts" / "backtests"

DATA_DIRECTORIES = {
    "M5": {
        "data": ROOT / "artifacts" / "data_m5",
        "m1": ROOT / "artifacts" / "data_m1",
    },
    "M15": {
        "data": ROOT / "artifacts" / "data_m15",
        "m1": ROOT / "artifacts" / "data_m1",
    },
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


def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
        except OSError:
            return {}
    return {}


def _read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except (pd.errors.ParserError, OSError):
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
        "orders_csv": _read_csv(run_dir / "orders.csv"),
        "manifest": _read_json(run_dir / "manifest.json"),
    }


st.set_page_config(page_title="TradeRunner Backtest Dashboard", layout="wide")

selected_run: str | None = None

with st.sidebar:
    st.header("Run configuration")
    timeframe = st.selectbox("Timeframe", tuple(DATA_DIRECTORIES.keys()), index=0)
    timeframe_paths = DATA_DIRECTORIES[timeframe]
    data_directory = timeframe_paths["data"]
    data_directory_m1 = timeframe_paths["m1"]
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

    pending_run_name_key = "run_name_pending"
    pending_scope_key = "run_name_pending_scope"
    if pending_run_name_key in st.session_state:
        st.session_state[run_name_key] = st.session_state.pop(pending_run_name_key)
        if pending_scope_key in st.session_state:
            st.session_state[run_name_scope_key] = st.session_state.pop(pending_scope_key)

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
        selected_meta = INSIDE_BAR_METADATA
        mode_value = selected_meta.name

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
                    payload_mode = yaml_payload.get("mode") if isinstance(yaml_payload, dict) else None
                    if isinstance(payload_mode, str) and payload_mode in STRATEGY_REGISTRY:
                        mode_value = payload_mode
                        selected_meta = STRATEGY_REGISTRY[mode_value]
        else:
            st.caption("Override core replay parameters directly.")
            mode_col, doc_col = st.columns([3, 1])
            modes = list(STRATEGY_REGISTRY.values())
            mode_labels = [meta.label for meta in modes]
            default_idx = next((i for i, meta in enumerate(modes) if meta.name == INSIDE_BAR_METADATA.name), 0)
            with mode_col:
                selected_label = st.selectbox(
                    "Strategy mode",
                    mode_labels,
                    index=default_idx,
                )
                selected_meta = next(meta for meta in modes if meta.label == selected_label)
                mode_value = selected_meta.name
            with doc_col:
                doc_path = selected_meta.doc_path
                if doc_path and doc_path.exists():
                    pdf_bytes = doc_path.read_bytes()
                    st.download_button(
                        label="📄 Spec",
                        data=pdf_bytes,
                        file_name=doc_path.name,
                        mime="application/pdf",
                        key=f"doc_{mode_value}",
                    )

            orders_csv = st.text_input(
                "Orders CSV",
                str(ROOT / "artifacts/orders/current_orders.csv"),
            )
            data_path = st.text_input(
                "Data directory",
                str(data_directory),
            )
            data_path_m1 = st.text_input(
                "M1 data directory",
                str(data_directory_m1),
            )
            tz_value = st.text_input("Timezone", selected_meta.timezone)

            rudometkin_universe_path: str | None = None
            if selected_meta.name == RUDOMETKIN_METADATA.name:
                default_universe = selected_meta.default_strategy_config.get(
                    "universe_path", str(RUDOMETKIN_UNIVERSE_DEFAULT)
                )
                rudometkin_universe_path = st.text_input(
                    "Rudometkin universe parquet",
                    default_universe,
                    help="Parquet file listing symbols when running the Rudometkin MOC strategy.",
                    key="rudometkin_universe_path",
                )

            costs_defaults = selected_meta.default_payload.get("costs", {})
            fees_default = float(costs_defaults.get("fees_bps", 0.0))
            slippage_default = float(costs_defaults.get("slippage_bps", 0.0))
            initial_cash_default = float(selected_meta.default_payload.get("initial_cash", DEFAULT_INITIAL_CASH))

            fees_bps = st.number_input("Fees (bps)", value=fees_default, step=0.1)
            slippage_bps = st.number_input("Slippage (bps)", value=slippage_default, step=0.1)
            initial_cash = st.number_input("Initial cash", value=initial_cash_default, step=1_000.0)

            default_sizing = selected_meta.default_sizing or {}
            risk_pct_default = float(default_sizing.get("risk_pct", 1.0))
            risk_pct_value = st.number_input(
                "Risk % per trade",
                value=risk_pct_default,
                step=0.1,
                min_value=0.1,
                max_value=10.0,
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
                **selected_meta.default_payload,
                "mode": mode_value,
                "orders_source_csv": orders_csv,
                "data": {
                    "path": data_path,
                    "path_m1": data_path_m1,
                    "tz": tz_value,
                },
                "costs": {
                    "fees_bps": float(fees_bps),
                    "slippage_bps": float(slippage_bps),
                },
                "initial_cash": float(initial_cash),
                "risk_pct": float(risk_pct_value),
            }
            if rudometkin_universe_path is not None:
                rudometkin_path_clean = rudometkin_universe_path.strip()
                if rudometkin_path_clean:
                    config_payload.setdefault("strategy_config", {})[
                        "universe_path"
                    ] = rudometkin_path_clean
            elif selected_meta.default_strategy_config:
                config_payload.setdefault("strategy_config", {}).update(
                    selected_meta.default_strategy_config
                )
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
                data_dir_m1=data_directory_m1,
            )

            strategy_meta = selected_meta

            pipeline = PipelineConfig(
                run_name=run_name,
                fetch=fetch_config,
                symbols=symbol_set,
                strategy=strategy_meta,
                config_path=config_path_for_run,
                config_payload=config_payload,
            )

            st.session_state["pipeline_log"] = []
            new_run = execute_pipeline(pipeline)
            finished_at = pd.Timestamp.now(tz=INSIDE_BAR_TIMEZONE).isoformat()
            st.success(f"Run finished → {new_run} at {finished_at}")
            st.session_state[pending_run_name_key] = f"ui_{timeframe.lower()}_{int(pd.Timestamp.utcnow().timestamp())}"
            st.session_state[pending_scope_key] = timeframe
            st.cache_data.clear()
            st.session_state["selected_run"] = new_run
            st.rerun()
        except Exception as exc:  # pragma: no cover - UI diagnostic handling
            logging.exception("Pipeline execution failed")
            st.error(f"Pipeline execution failed: {exc}")
            st.code(traceback.format_exc())
            st.stop()

    log_entries = st.session_state.get("pipeline_log", [])
    if log_entries:
        st.markdown("### Last run output")
        for idx, entry in enumerate(log_entries, start=1):
            title = entry.get("title") or f"Step {idx}"
            with st.expander(f"{idx}) {title}", expanded=False):
                status = entry.get("status")
                if status:
                    st.write(f"Status: `{status}`")
                if entry.get("kind") == "command":
                    cmd_display = entry.get("command") or "(no command)"
                    st.code(cmd_display)
                    rc = entry.get("return_code")
                    if rc is not None:
                        st.write(f"Return code: `{rc}`")
                    duration = entry.get("duration")
                    if duration is not None:
                        st.write(f"Duration: `{duration:.2f}s`")
                    output = entry.get("output")
                    if output:
                        st.text(output)
                else:
                    message = entry.get("message")
                    if message:
                        st.write(message)
                    duration = entry.get("duration")
                    if duration is not None:
                        st.write(f"Duration: `{duration:.2f}s`")

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
        except (KeyError, ValueError, TypeError) as exc:
            st.info(f"Equity data could not be plotted ({exc}).")
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
        except (KeyError, ValueError, TypeError) as exc:
            st.info(f"Drawdown data could not be plotted ({exc}).")
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


tabs = st.tabs(["Orders", "Filled Orders", "Trades"])
orders_df = run["orders_csv"]
with tabs[0]:
    if orders_df is not None and not orders_df.empty:
        display_orders = orders_df.copy()
        for column in ["price", "stop_loss", "take_profit"]:
            if column in display_orders.columns:
                display_orders[column] = display_orders[column].astype(float).round(2)
        st.dataframe(display_orders, width="stretch", height=360)
    else:
        st.info("No orders available.")

with tabs[1]:
    filled_df = run["fills_csv"]
    if filled_df is not None and not filled_df.empty:
        display_fills = filled_df.copy()
        if {"entry_price", "qty"}.issubset(display_fills.columns):
            display_fills["entry_notional"] = (display_fills["entry_price"].astype(float) * display_fills["qty"].astype(float)).round(2)
        for column in ["fees_entry", "fees_exit", "fees_total", "slippage_entry", "slippage_exit", "slippage_total"]:
            if column in display_fills.columns:
                display_fills[column] = display_fills[column].astype(float).round(2)
        st.dataframe(display_fills, width="stretch", height=360)
    else:
        st.info("No fills available.")

with tabs[2]:
    trades_df = run["trades_csv"]
    if trades_df is not None and not trades_df.empty:
        display_trades = trades_df.copy()
        for column in ["fees_entry", "fees_exit", "fees_total", "slippage_entry", "slippage_exit", "slippage_total"]:
            if column in display_trades.columns:
                display_trades[column] = display_trades[column].astype(float).round(2)
        st.dataframe(display_trades, width="stretch", height=360)
    else:
        st.info("No trades available.")
