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


def _render_strategy_selector() -> tuple["StrategyMetadata", str]:
    st.header("1. Strategy Selection")

    modes = list(STRATEGY_REGISTRY.values())
    mode_labels = [meta.label for meta in modes]
    default_idx = next((i for i, meta in enumerate(modes) if meta.name == RUDOMETKIN_METADATA.name), 0)

    selected_label = st.selectbox(
        "Strategy",
        mode_labels,
        index=default_idx,
        key="strategy_select_main",
    )
    selected_meta = next(meta for meta in modes if meta.label == selected_label)
    mode_value = selected_meta.name

    doc_path = selected_meta.doc_path
    if doc_path and doc_path.exists():
        pdf_bytes = doc_path.read_bytes()
        st.download_button(
            label="📄 Download Strategy Spec",
            data=pdf_bytes,
            file_name=doc_path.name,
            mime="application/pdf" if doc_path.suffix == ".pdf" else "text/markdown",
            key=f"doc_{mode_value}",
        )

    return selected_meta, mode_value


def _render_universe_and_symbols(
    selected_meta,
    data_directory: Path,
) -> tuple[list[str], list[str], list[str], str | None]:
    symbol_preview: List[str] = []
    symbol_preview_errors: List[str] = []
    universe_symbols: List[str] = []
    rudometkin_universe_path: str | None = None

    if selected_meta.name == RUDOMETKIN_METADATA.name:
        st.subheader("Universe Selection")
        default_universe = selected_meta.default_strategy_config.get(
            "universe_path", str(RUDOMETKIN_UNIVERSE_DEFAULT)
        )
        rudometkin_universe_path = st.text_input(
            "Universe Parquet File",
            default_universe,
            help=(
                "Path to parquet file. Must contain symbols either as a column "
                "(e.g., 'symbol', 'ticker') or in MultiIndex level 0."
            ),
            key="rudometkin_universe_path",
        )

        load_universe = st.checkbox("Load symbols from Universe", value=True)
        if load_universe and rudometkin_universe_path:
            u_path = Path(rudometkin_universe_path)
            if not u_path.is_absolute():
                u_path = ROOT / u_path

            if u_path.exists():
                try:
                    u_df = pd.read_parquet(u_path)
                    u_cols = u_df.columns

                    sym_col = next((c for c in ["symbol", "Symbol", "ticker", "Ticker"] if c in u_cols), None)
                    if not sym_col:
                        sym_col = next(
                            (
                                c
                                for c in u_cols
                                if u_df[c].dtype == object or pd.api.types.is_string_dtype(u_df[c])
                            ),
                            None,
                        )

                    if sym_col:
                        universe_symbols = (
                            u_df[sym_col]
                            .dropna()
                            .astype(str)
                            .str.strip()
                            .str.upper()
                            .unique()
                            .tolist()
                        )
                        universe_symbols = sorted(universe_symbols)
                        st.success(f"Loaded {len(universe_symbols)} symbols from universe columns.")
                    elif isinstance(u_df.index, pd.MultiIndex):
                        level_0 = u_df.index.get_level_values(0)
                        if pd.api.types.is_string_dtype(level_0) or level_0.dtype == object:
                            universe_symbols = sorted(
                                level_0.unique().astype(str).str.strip().str.upper().tolist()
                            )
                            st.success(f"Loaded {len(universe_symbols)} symbols from universe index.")
                    elif u_df.index.dtype == object or pd.api.types.is_string_dtype(u_df.index):
                        universe_symbols = sorted(
                            u_df.index.unique().astype(str).str.strip().str.upper().tolist()
                        )
                        st.success(f"Loaded {len(universe_symbols)} symbols from universe index.")

                    if not universe_symbols:
                        if "ts_id" in u_cols:
                            st.error(
                                "Found 'ts_id' but no 'symbol' column/index. "
                                "Please provide a file with a symbol column."
                            )
                        else:
                            st.error("Could not identify symbol column in universe file.")
                except Exception as exc:  # pragma: no cover - defensive
                    st.error(f"Failed to read universe file: {exc}")
            else:
                st.warning(f"Universe file not found: {u_path}")

        with st.expander("Manual Symbol Override (Optional)"):
            symbol_input = st.text_area(
                "Additional Symbols",
                value="",
                height=60,
                placeholder="Enter comma separated tickers to add...",
            ).strip()
            manual_syms, manual_errors = collect_symbols([], symbol_input)
            symbol_preview_errors.extend(manual_errors)
            if manual_syms:
                universe_symbols = sorted(list(set(universe_symbols) | set(manual_syms)))
                st.info(f"Total symbols including manual: {len(universe_symbols)}")

    else:
        st.subheader("Symbol Selection")
        cached_symbols = list_symbols(str(data_directory))
        cached_selection = st.multiselect(
            "Select cached symbols",
            cached_symbols,
            help="Symbols already downloaded.",
        )

        symbol_input = st.text_area(
            "Manual Entry",
            value="",
            height=80,
            placeholder="Enter comma or newline separated tickers (e.g. TSLA, AAPL)",
        ).strip()

        symbol_preview, symbol_preview_errors = collect_symbols(cached_selection, symbol_input)
        if symbol_preview:
            st.markdown(f"**Selected:** {len(symbol_preview)} symbols")
            with st.expander("View List"):
                st.write(", ".join(symbol_preview))
        else:
            st.info("No symbols selected.")

        for msg in symbol_preview_errors:
            st.warning(msg)

    return symbol_preview, symbol_preview_errors, universe_symbols, rudometkin_universe_path


def _render_insidebar_parameters(selected_meta) -> dict:
    st.divider()
    st.header("📊 InsideBar Parameters")

    defaults = selected_meta.default_strategy_config or {}

    with st.expander("Entry & Exit Settings", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            initial_cash = selected_meta.default_payload.get("initial_cash")
            risk_cfg = selected_meta.default_sizing or {}
            st.caption(
                f"Initial cash: {initial_cash}, risk mode: {risk_cfg.get('mode', 'risk')} "
                f"@ {risk_cfg.get('risk_pct', 1.0)}%"
            )
        with col2:
            st.info("Parameters currently fixed to canonical spec; UI overrides coming soon.")

    if defaults:
        with st.expander("Effective Defaults", expanded=False):
            st.json(defaults)

    st.caption("⚙️ Additional settings available in Advanced Parameters below")
    return defaults


def _render_rudometkin_parameters() -> dict:
    st.divider()
    st.header("📈 Rudometkin Strategy Parameters")

    rk_config: dict = st.session_state.setdefault("rk_config", {})

    with st.expander("Entry & Exit Settings (LONG/SHORT)", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_discount_pct = st.number_input(
                "Long: Entry Discount %",
                min_value=0.0,
                max_value=10.0,
                value=rk_config.get("entry_stretch1", 0.035) * 100,
                step=0.1,
                help="Limit price = Close * (1 - discount). 3.5% → 0.965 * Close.",
            )
            rk_config["entry_stretch1"] = entry_discount_pct / 100.0
        with col2:
            pullback_pct = st.number_input(
                "Long: Min Intraday Pullback %",
                min_value=0.0,
                max_value=50.0,
                value=rk_config.get("long_pullback_threshold", 0.03) * 100,
                step=0.1,
                help="(Open - Close)/Open threshold for long pullbacks.",
            )
            rk_config["long_pullback_threshold"] = pullback_pct / 100.0
        with col3:
            entry_premium_pct = st.number_input(
                "Short: Entry Premium %",
                min_value=0.0,
                max_value=10.0,
                value=rk_config.get("entry_stretch2", 0.05) * 100,
                step=0.1,
                help="Limit price = Close * (1 + premium) for shorts.",
            )
            rk_config["entry_stretch2"] = entry_premium_pct / 100.0

    with st.expander("Trend & Volatility Filters", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            rk_config["adx_period"] = st.number_input(
                "ADX Period",
                min_value=2,
                max_value=50,
                value=rk_config.get("adx_period", 5),
                step=1,
            )
            rk_config["adx_threshold"] = st.number_input(
                "Min ADX",
                min_value=0.0,
                max_value=100.0,
                value=rk_config.get("adx_threshold", 35.0),
                step=1.0,
            )
            rk_config["sma_period"] = st.number_input(
                "Trend SMA Period",
                min_value=50,
                max_value=400,
                value=rk_config.get("sma_period", 200),
                step=10,
            )
        with col2:
            # ATR ratios - store as nested dicts for config schema compatibility
            atr40_bounds = rk_config.get("atr40_ratio_bounds", {"min": 0.01, "max": 0.10})
            atr40_min = st.number_input(
                "ATR40/Close Min %",
                min_value=0.0,
                max_value=100.0,
                value=atr40_bounds.get("min", 0.01) * 100,
                step=0.1,
                format="%.1f",
            )
            atr40_max = st.number_input(
                "ATR40/Close Max %",
                min_value=0.0,
                max_value=100.0,
                value=atr40_bounds.get("max", 0.10) * 100,
                step=1.0,
                format="%.1f",
            )
            rk_config["atr40_ratio_bounds"] = {"min": atr40_min / 100.0, "max": atr40_max / 100.0}
            
            atr2_bounds = rk_config.get("atr2_ratio_bounds", {"min": 0.01, "max": 0.20})
            atr2_min = st.number_input(
                "ATR2/Close Min %",
                min_value=0.0,
                max_value=100.0,
                value=atr2_bounds.get("min", 0.01) * 100,
                step=0.1,
                format="%.1f",
            )
            atr2_max = st.number_input(
                "ATR2/Close Max %",
                min_value=0.0,
                max_value=100.0,
                value=atr2_bounds.get("max", 0.20) * 100,
                step=1.0,
                format="%.1f",
            )
            rk_config["atr2_ratio_bounds"] = {"min": atr2_min / 100.0, "max": atr2_max / 100.0}

    with st.expander("Universe & Daily Finder", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            rk_config["min_price"] = st.number_input(
                "Min Close Price",
                min_value=0.0,
                max_value=1000.0,
                value=rk_config.get("min_price", 10.0),
                step=1.0,
            )
        with col2:
            rk_config["min_average_volume"] = st.number_input(
                "Min 50d Avg Volume",
                min_value=0,
                max_value=100_000_000,
                value=int(rk_config.get("min_average_volume", 1_000_000)),
                step=50_000,
            )
        with col3:
            rk_config["max_daily_signals"] = st.number_input(
                "Max Signals per Day (Long/Short)",
                min_value=1,
                max_value=100,
                value=int(rk_config.get("max_daily_signals", 10)),
                step=1,
            )

    with st.expander("Advanced Indicator Settings", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            rk_config["crsi_rank_period"] = st.number_input(
                "ConnorsRSI Rank Lookback",
                min_value=10,
                max_value=250,
                value=int(rk_config.get("crsi_rank_period", 100)),
                step=5,
            )
            rk_config["crsi_price_rsi"] = st.number_input(
                "ConnorsRSI Price RSI Len",
                min_value=2,
                max_value=20,
                value=int(rk_config.get("crsi_price_rsi", 2)),
                step=1,
            )
        with col2:
            rk_config["crsi_streak_rsi"] = st.number_input(
                "ConnorsRSI Streak RSI Len",
                min_value=2,
                max_value=20,
                value=int(rk_config.get("crsi_streak_rsi", 2)),
                step=1,
            )
            rk_config["crsi_threshold"] = st.number_input(
                "Min ConnorsRSI for Shorts",
                min_value=0.0,
                max_value=100.0,
                value=rk_config.get("crsi_threshold", 70.0),
                step=1.0,
            )

    return rk_config

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
    selected_meta, mode_value = _render_strategy_selector()

    st.divider()
    st.header("2. Data Configuration")

    timeframe = st.selectbox("Timeframe", tuple(DATA_DIRECTORIES.keys()), index=0)
    timeframe_paths = DATA_DIRECTORIES[timeframe]
    data_directory = timeframe_paths["data"]
    data_directory_m1 = timeframe_paths["m1"]

    symbol_preview, symbol_preview_errors, universe_symbols, rudometkin_universe_path = _render_universe_and_symbols(
        selected_meta,
        data_directory,
    )

    defaults_for_insidebar: dict = {}
    rk_config: dict | None = None

    if selected_meta.name in [INSIDE_BAR_METADATA.name, "insidebar_intraday_v2"]:
        _render_insidebar_parameters(selected_meta)
    elif selected_meta.name == RUDOMETKIN_METADATA.name:
        _render_rudometkin_parameters()


    st.divider()
    st.header("3. Run Settings")
    
    use_sample = st.checkbox("Use synthetic data", value=False)
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

    run_name = st.text_input("Run Name", value=st.session_state[run_name_key], key=run_name_key)

    with st.expander("Advanced Parameters", expanded=False):
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
                    st.json(yaml_payload)
        else:
            # Manual Parameters
            config_payload = {}

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
            
            # Apply strategy-specific configuration
            if selected_meta.name == RUDOMETKIN_METADATA.name:
                # Get config from session state (set in the RK config section above)
                rk_config = st.session_state.get("rk_config", {})
                
                # Strategy-specific params
                config_payload["strategy_config"] = {
                    "entry_stretch1": rk_config.get("entry_stretch1", 0.035),
                    "entry_stretch2": rk_config.get("entry_stretch2", 0.05),
                    "long_pullback_threshold": rk_config.get("long_pullback_threshold", 0.03),
                    "crsi_threshold": rk_config.get("crsi_threshold", 70.0),
                    "adx_threshold": rk_config.get("adx_threshold", 35.0),
                    "adx_period": rk_config.get("adx_period", 5),
                    "sma_period": rk_config.get("sma_period", 200),
                    "atr40_ratio_bounds": rk_config.get("atr40_ratio_bounds", {"min": 0.01, "max": 0.10}),
                    "atr2_ratio_bounds": rk_config.get("atr2_ratio_bounds", {"min": 0.01, "max": 0.20}),
                    "min_price": rk_config.get("min_price", 10.0),
                    "min_average_volume": rk_config.get("min_average_volume", 1_000_000),
                    "crsi_price_rsi": rk_config.get("crsi_price_rsi", 2),
                    "crsi_streak_rsi": rk_config.get("crsi_streak_rsi", 2),
                    "crsi_rank_period": rk_config.get("crsi_rank_period", 100),
                }
                
                # Pipeline-level setting
                config_payload["max_daily_signals"] = rk_config.get("max_daily_signals", 10)
                
                # Universe path
                if rudometkin_universe_path:
                    rudometkin_path_clean = rudometkin_universe_path.strip()
                    if rudometkin_path_clean:
                        config_payload["strategy_config"]["universe_path"] = rudometkin_path_clean
            
            elif selected_meta.name in [INSIDE_BAR_METADATA.name, "insidebar_intraday_v2"]:
                # InsideBar strategies - use defaults from metadata
                # Future: Add configurable parameters here
                if selected_meta.default_strategy_config:
                    config_payload["strategy_config"] = dict(selected_meta.default_strategy_config)
            
            config_path_for_run = None

        # Optional: show the final merged configuration for transparency
        if config_payload is not None:
            with st.expander("Preview effective config payload", expanded=False):
                st.json(config_payload)

    if st.button("Start backtest", type="primary", width="stretch"):
        try:
            validation_errors: List[str] = []

            symbol_set = sorted(list(set(symbol_preview) | set(universe_symbols)))
            if symbol_set:
                filtered_errors = [msg for msg in symbol_preview_errors if "Select or enter at least one valid symbol." not in msg]
                validation_errors.extend(filtered_errors)
            else:
                validation_errors.append("No symbols selected. Please check your Universe file or add symbols manually.")
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
