% Rudometkin MOC Strategy – Technical Handover

> **📜 HISTORICAL DOCUMENT**
> **Date**: November 2025
> **Context**: Initial Rudometkin MOC strategy handover documentation

> Key focus: new minute‑data logic, two‑stage pipeline, and manifest‑compliant design

---

## 1. Executive Summary

The Rudometkin MOC (Market‑On‑Close) strategy is implemented as a **two‑stage pipeline**:

1. **Stage 1 – Daily Universe Scan (D1)**
   - Loads a universe parquet with daily OHLCV data for many symbols.
   - Applies Rudometkin filters (price, volume, ATR ranges, trend, ConnorsRSI, etc.).
   - Ranks and selects at most `max_daily_signals` per direction (LONG/SHORT) per day.
   - Persists a daily signals CSV and returns the **filtered symbol list**.

2. **Stage 2 – Intraday Backtest (M5/M15 using M1 data)**
   - Fetches **M1 intraday data** only for the selected symbols.
   - Resamples M1 → M5/M15 for signal generation, while executions use M1 for fills.
   - Runs the generic backtest engine (replay) and produces fills, trades, and orders.

The pipeline is **capability‑driven**, not strategy‑name driven:

- `StrategyMetadata.requires_universe=True`
- `StrategyMetadata.supports_two_stage_pipeline=True`
- A strategy‑agnostic `strategy_hooks` registry wires the Rudometkin daily scan into
  the generic `execute_pipeline`.

Minute data (M1) is now the **source of truth for execution timing**, while M5/M15
are used for signal definitions. This fixes earlier robustness issues where:

- Signals were generated but execution timing was ambiguous.
- Historical coverage was too short, leading to **0 candidates**.

We now use a **300‑day historical lookback buffer** for daily indicators, which
allows the Rudometkin filters to warm up correctly and yield thousands of
short‑candidates plus a smaller set of long‑candidates.

---

## 2. Architecture Overview

### 2.1 Strategy Metadata & Capabilities

File: `apps/streamlit/state.py`

```python
@dataclass
class StrategyMetadata:
    name: str
    label: str
    timezone: str
    sessions: List[str]
    signal_module: str
    orders_source: Path
    default_payload: Dict
    strategy_name: str
    doc_path: Optional[Path] = None
    default_sizing: Optional[Dict] = None
    default_strategy_config: Dict[str, Any] = field(default_factory=dict)
    requires_universe: bool = False
    supports_two_stage_pipeline: bool = False


RUDOMETKIN_UNIVERSE_DEFAULT = ROOT / "data" / "universe" / "rudometkin.parquet"

RUDOMETKIN_METADATA = StrategyMetadata(
    name="rudometkin_moc_mode",
    label="Rudometkin MOC",
    timezone="Europe/Berlin",
    sessions=["15:30-22:00"],
    signal_module="signals.cli_rudometkin_moc",
    orders_source=ROOT / "artifacts" / "signals" / "current_signals_rudometkin.csv",
    default_payload={
        "engine": "replay",
        "mode": "rudometkin_moc_mode",
        "data": {"tz": "America/New_York"},
        "costs": INSIDE_BAR_DEFAULTS.costs,
        "initial_cash": INSIDE_BAR_DEFAULTS.initial_cash,
        "strategy": "rudometkin_moc",
    },
    strategy_name="rudometkin_moc",
    doc_path=ROOT / "docs" / "rudometkin_moc_long_short_translation.md",
    default_sizing={
        "mode": "risk",
        "risk_pct": INSIDE_BAR_DEFAULTS.risk_pct,
        "min_qty": INSIDE_BAR_DEFAULTS.min_qty,
    },
    default_strategy_config={
        "universe_path": str(RUDOMETKIN_UNIVERSE_DEFAULT)
    },
    requires_universe=True,
    supports_two_stage_pipeline=True,
)
```

Key points:

- Capabilities describe **what** the strategy needs (`requires_universe`,
  `supports_two_stage_pipeline`), not **who** it is (no `is_rudometkin`).
- `default_strategy_config["universe_path"]` is the canonical source of truth for
  where the daily universe parquet lives.

### 2.2 Strategy Hooks Registry (Two‑Stage Pipelines)

File: `src/strategies/__init__.py`

```python
from collections.abc import Callable
from typing import Any, Dict, Optional

from .base import IStrategy, Signal, StrategyConfig
from .registry import registry

DailyScanHook = Callable[[Any, int], list[str]]  # (pipeline, max_daily) -> symbols


class StrategyHooks:
    """Registry for optional strategy-specific pipeline hooks."""

    def __init__(self) -> None:
        self._daily_scan: Dict[str, DailyScanHook] = {}

    def register_daily_scan(self, strategy_name: str, hook: DailyScanHook) -> None:
        self._daily_scan[strategy_name] = hook

    def get_daily_scan(self, strategy_name: str) -> Optional[DailyScanHook]:
        return self._daily_scan.get(strategy_name)


strategy_hooks = StrategyHooks()
```

This registry allows `execute_pipeline` to route to a strategy‑specific daily scan
purely based on capabilities + `strategy_name`, without any hard‑coded strategy
branches.

### 2.3 Two‑Stage Pipeline Execution

File: `apps/streamlit/pipeline.py`

```python
from strategies import factory, registry, strategy_hooks


def execute_pipeline(pipeline: PipelineConfig) -> str:
    run_started_at = datetime.now(timezone.utc).isoformat()
    _store_log({
        "kind": "run_meta",
        "phase": "start",
        "run_name": pipeline.run_name,
        "strategy": pipeline.strategy.strategy_name,
        "symbols": list(pipeline.symbols),
        "timeframe": pipeline.fetch.timeframe,
        "started_at": run_started_at,
    })

    # --- Two-Stage Pipeline (Capability + Hook-Based) ---
    if pipeline.strategy.supports_two_stage_pipeline:
        daily_scan = strategy_hooks.get_daily_scan(pipeline.strategy.strategy_name)
        if daily_scan is None:
            show_step_message(
                "0) Daily Scan",
                f"No daily_scan hook registered for strategy '{pipeline.strategy.strategy_name}'.",
                status="error",
            )
            return "No Candidates"

        max_daily = 10
        if pipeline.config_payload and "max_daily_signals" in pipeline.config_payload:
            try:
                max_daily = int(pipeline.config_payload["max_daily_signals"])
            except (TypeError, ValueError):
                pass

        filtered_symbols = daily_scan(pipeline, max_daily)

        if filtered_symbols:
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
    # 1) Fetch M1 intraday only for filtered symbols
    # 2) Signals on M5/M15 (resampled from M1)
    # 3) Orders export and replay backtest
```

The generic pipeline now only knows about **capabilities** and **hooks**; all
Rudometkin specifics live in its own pipeline module.

---

## 3. Rudometkin Daily Scan & Minute Data Logic

### 3.1 Daily Universe Scan (Stage 1)

File: `src/strategies/rudometkin_moc/pipeline.py`

```python
from strategies import strategy_hooks


def run_daily_scan(
    pipeline,  # PipelineConfig – intentionally untyped to avoid circular import
    max_daily_signals: int = 10,
) -> List[str]:
    """Execute daily universe scan and filtering for Rudometkin strategy."""

    from strategies import factory, registry

    ROOT = Path(__file__).resolve().parents[3]

    _show_step_message("0) Daily Scan", "Starting Stage 1: Daily Universe Scan & Filter")

    strategy_config: Dict[str, Any] = {}
    if pipeline.config_payload and isinstance(pipeline.config_payload, dict):
        strategy_config = dict(pipeline.config_payload.get("strategy_config", {}) or {})
    if not strategy_config and pipeline.strategy.default_strategy_config:
        strategy_config = dict(pipeline.strategy.default_strategy_config)

    universe_path = strategy_config.get("universe_path")
    if not universe_path:
        _show_step_message(
            "0.1) universe",
            "Universe path not configured for Rudometkin strategy.",
            status="error",
        )
        return []

    universe_path = Path(universe_path)
    if not universe_path.is_absolute():
        universe_path = ROOT / universe_path

    if not universe_path.exists():
        _show_step_message(
            "0.1) universe",
            f"Universe parquet not found: {universe_path}",
            status="error",
        )
        return []

    try:
        universe_df = pd.read_parquet(universe_path)
    except (OSError, FileNotFoundError, ValueError) as exc:
        _show_step_message(
            "0.1) universe",
            f"Failed to load universe parquet {universe_path}: {type(exc).__name__}: {exc}",
            status="error",
        )
        return []

    # Handle MultiIndex or column-based symbol/date
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
        _show_step_message(
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
        _show_step_message("0.1) universe", "Universe parquet is empty.", status="warning")
        return []

    # Apply date range filter (with sufficient historical depth – 300d lookback
    # is ensured upstream in the data generation pipeline)
    if pipeline.fetch.start:
        start_date = pd.Timestamp(pipeline.fetch.start).date()
        universe_df = universe_df[universe_df["timestamp"].dt.date >= start_date]
    if pipeline.fetch.end:
        end_date = pd.Timestamp(pipeline.fetch.end).date()
        universe_df = universe_df[universe_df["timestamp"].dt.date <= end_date]

    requested_symbols = {sym.upper() for sym in pipeline.symbols} if pipeline.symbols else set()
    if requested_symbols:
        universe_df = universe_df[universe_df["symbol"].isin(requested_symbols)]
    ...
```

The **300‑day historical lookback** is handled at the **data staging level** for
the universe parquet (not repeated here for brevity). The key change is that
Stage 1 no longer depends on remote fetches for daily bars on the fly; it uses a
pre‑generated universe parquet with adequate history.

### 3.2 Minute Data Usage (Stage 2)

Once Stage 1 returns `filtered_symbols`, Stage 2 runs the generic intraday
pipeline using **M1 as the base timeframe**:

- `FetchConfig` is updated to `symbols=filtered_symbols`.
- `axiom_bt.cli_data ensure-intraday` fetches/ensures **M1** for those symbols.
- Signals are generated on M5/M15 (resampled from M1) via Rudometkin’s signal
  CLI.
- The replay engine uses M1 for execution timestamps and fills.

This solves previous issues where M5 aggregation masked intra‑bar ordering and
made execution timing ambiguous.

---

## 4. Testing & Diagnostics

### 4.1 Unit Tests

Relevant tests (all passing as of this handover):

- `tests/test_rudometkin_moc_strategy.py`
  - Long/short signal generation logic.
  - Universe column and universe path filters.
  - Failure‑path for malformed universe parquet.

- `tests/test_strategy_separation.py`
  - Capability flags on `StrategyMetadata`.
  - Strategy isolation (Inside Bar vs Rudometkin).
  - Existence and importability of `strategies.rudometkin_moc.pipeline`.
  - Streamlit‑independent pipeline import via `HAS_STREAMLIT`.

### 4.2 Run Logs & Performance

For every backtest run, `execute_pipeline` writes:

- `artifacts/backtests/<run_name>/run_log.json`

Structure:

```jsonc
{
  "run_name": "run_2025...",
  "strategy": "rudometkin_moc",
  "symbols": ["..."],
  "timeframe": "M5",
  "created_at": "...",
  "entries": [
    {
      "kind": "run_meta",
      "phase": "start",
      "run_name": "...",
      "strategy": "rudometkin_moc",
      "symbols": ["..."],
      "timeframe": "M5",
      "started_at": "..."
    },
    {
      "kind": "command",
      "title": "0) ensure-intraday",
      "command": "python -m axiom_bt.cli_data ...",
      "return_code": 0,
      "status": "success",
      "duration": 12.34,
      "output": "..."
    },
    ...
  ]
}
```

You can inspect performance via:

```bash
PYTHONPATH=src python -m cli.log_inspect artifacts/backtests/<run_name>/run_log.json
```

Or in the Streamlit dashboard via the **"Run log & performance"** expander for a
selected run (per‑step duration table + raw log view).

---

## 5. Known Issues & Future Work

1. **Universe parquet freshness**
   - The current design assumes the universe parquet is generated with
     sufficient and recent history (e.g. last 300+ days).
   - There is no automatic refresh inside Stage 1; refresh is an upstream
     responsibility.

2. **Multiple universe‑based strategies**
   - The hook registry (`strategy_hooks`) supports additional strategies, but
     only `rudometkin_moc` registers `run_daily_scan` today.
   - Adding a new universe‑based strategy should follow the same pattern:
     define metadata capabilities, implement `pipeline.run_daily_scan`, and
     register it in `strategy_hooks`.

3. **Additional failure‑mode tests**
   - The most important failure paths are covered (missing universe, malformed
     columns, empty universe). More coverage can be added for extreme edge
     cases (e.g. NaN‑heavy daily bars, single‑symbol universes).

---

## 6. Quick Run Book

### 6.1 Run Rudometkin Backtest via UI

1. Start dashboard:

   ```bash
   PYTHONPATH=src streamlit run apps/streamlit/app.py
   ```

2. In the sidebar:
   - **Strategy Selection**: choose "Rudometkin MOC".
   - **Data Configuration**: ensure the universe parquet path points to a file
     with at least 300 days of daily data.
   - Configure any desired Rudometkin parameters (max signals per day, etc.).

3. In **Advanced Parameters**:
   - Use Manual or YAML config as preferred.
   - Check the "📋 Preview Effective Configuration" expander to verify the
     final payload.

4. Click **"Start backtest"**.

5. Inspect results:
   - Equity/drawdown charts.
   - Orders / Filled Orders / Trades tables.
   - "Run log & performance" expander for timings and step logs.

### 6.2 Verify Rudometkin Logic via Tests

From repo root:

```bash
make test       # or: PYTHONPATH=src python -m pytest tests
make test-cov   # with coverage
```

Focus on:

- `tests/test_rudometkin_moc_strategy.py`
- `tests/test_strategy_separation.py`

These confirm the daily + intraday logic and the architectural separation.
