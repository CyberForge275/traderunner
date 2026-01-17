# Forensic Audit: Pipeline Signal Columns & Strategy Attachment

- **Audit Date**: 2026-01-14
- **Auditor**: Antigravity (Forensic Code Auditor)
- **Repo**: `traderunner`
- **Scope**: `src/axiom_bt/pipeline/runner.py` and downstream signal generation.

---

## Executive Summary

1.  **Orchestrator Disconnect**: `run_pipeline` currently passes raw OHLCV bars directly to `generate_intent`, bypassing the `SignalFrameFactory`.
2.  **Mock Logic in Production**: `src/axiom_bt/pipeline/signals.py` implements a hardcoded mock logic for signal generation (`close > prev_close`) rather than utilizing strategy-specific logic.
3.  **Dormant Infrastructure**: Both `signal_frame_factory.py` and `InsideBarSignalHook` are implemented and registered but remain **unused** by the primary execution path.
4.  **Schema Ownership**: Architectural integrity is maintained; strategy-specific columns (e.g., `atr`, `inside_bar`) are correctly defined under `src/strategies/inside_bar/signal_schema.py`.
5.  **Artifact Ambiguity**: The `signals_frame.parquet` artifact currently contains only mock signal columns, lacking the intended technical indicators (ATR, Mother Bar ranges).
6.  **Missing Wiring**: No call to `build_signal_frame` exists in `runner.py`, preventing the attachment of strategy-owned schema columns.
7.  **Inert Validation**: `signal_frame_contract_v1.py` contains robust validation logic, but it is only invoked within the unused `InsideBarSignalHook`.
8.  **Insertion Point Identified**: A critical insertion point exists at `runner.py:L125` to wire the factory before intent generation.

---

## A) Current Pipeline Call Graph

The following sequence represents the execution flow in `src/axiom_bt/pipeline/runner.py::run_pipeline`:

1.  **`load_bars_snapshot`** (`src/axiom_bt/pipeline/data_prep.py`)
    - **Input**: `snapshot_path` (Path)
    - **Output**: `(bars: pd.DataFrame, bars_hash: str)`
    - **Note**: Loads the base OHLCV data.

2.  **`generate_intent`** (`src/axiom_bt/pipeline/signals.py`)
    - **Input**: `bars`, `strategy_id`, `strategy_version`, `params`
    - **Output**: `IntentArtifacts` (contains `signals_frame`, `events_intent`, `intent_hash`)
    - **Logic**: Implements **mock signal generation** (L58-L72). It constructs its own `signals_frame` locally (L74).
    - **DataFrame**: `signals_frame` (Cols: `timestamp`, `side`, `close`, `prev_close`, `symbol`).

3.  **`generate_fills`** (`src/axiom_bt/pipeline/fill_model.py`)
    - **Input**: `intent_art.events_intent`, `bars`
    - **Output**: `FillArtifacts` (contains `fills`, `fills_hash`)
    - **Logic**: Matches intent timestamps to bar prices.

4.  **`execute`** (`src/axiom_bt/pipeline/execution.py`)
    - **Input**: `fills_art.fills`, `intent_art.events_intent`, `initial_cash`, `compound_enabled`
    - **Output**: `ExecutionArtifacts` (contains `trades`, `equity_curve`, `portfolio_ledger`)
    - **Logic**: Applies sizing and builds trade records.

5.  **`compute_and_write_metrics`** (`src/axiom_bt/pipeline/metrics.py`)
    - **Input**: `exec_art.trades`, `exec_art.equity_curve`, `initial_cash`, `out_path`
    - **Output**: `metrics` (Dict)

6.  **`write_artifacts`** (`src/axiom_bt/pipeline/artifacts.py`)
    - **Input**: `out_dir`, multiple DataFrames including `signals_frame=intent_art.signals_frame`.
    - **Action**: Persists all frames to disk.
    - **Artifact**: `signals_frame.parquet`.

---

## B) Signal/Indicator Schema Ownership Check

### Findings:
- **Strategy Schema**: Strategy-specific columns are correctly isolated.
  - [src/strategies/inside_bar/signal_schema.py:L27-34](file:///home/mirko/data/workspace/droid/traderunner/src/strategies/inside_bar/signal_schema.py#L27-34) defines indicators like `atr`, `inside_bar`, `mother_high`.
- **Generic Primitives**: Base contract primitives live in `src/axiom_bt/contracts/`.
  - [src/axiom_bt/contracts/signal_frame_contract_v1.py:L24-29](file:///home/mirko/data/workspace/droid/traderunner/src/axiom_bt/contracts/signal_frame_contract_v1.py#L24-29) defines `ColumnSpec`.

### Schema Ownership Violations:
- **NONE FOUND**. The architecture properly separates strategy definitions from the backtesting engine. However, the engine currently ignores the strategy definitions.

---

## C) Where are columns actually attached today?

1.  **In `src/axiom_bt/pipeline/signals.py::generate_intent`**:
    - **Builds `signals_frame`?** YES (L74).
    - **Columns added?** `side`, `prev_close`. It does **not** include technical indicators.
    - **Strategy Hooks?** **NO**. It is pure mock logic (L38).

2.  **In `src/axiom_bt/pipeline/signal_frame_factory.py`**:
    - **Status**: **ORPHANED**.
    - **Imports**: Calls `axiom_bt.strategy_hooks.registry.get_hook` and `axiom_bt.contracts.signal_frame_contract_v1`.
    - **Validation**: Performs strict schema validation (L45).
    - **Observation**: This file is intended to be the entry point for attaching strategy columns but is never called by `runner.py`.

3.  **In `src/axiom_bt/strategy_hooks/*`**:
    - **Status**: **DORMANT**.
    - **Hooks**: `InsideBarSignalHook` is present and correctly implements `extend_signal_frame`.
    - **Wiring**: Registered in `src/axiom_bt/strategy_hooks/registry.py:L12`, but no pipeline component requests it.

4.  **In `write_artifacts`**:
    - **Persists `signals_frame`?** YES (L43).
    - **Source**: It writes the `signals_frame` generated by the mock logic in `signals.py`.

---

## D) Missing Insertion Point(s) in `run_pipeline`

To align with the architectural goal, the pipeline requires the following insertion point:

**Location**: `src/axiom_bt/pipeline/runner.py` at **Line 125** (between bar loading and intent generation).

### Required Logic (Abstracted):
1.  **Identify Hook**: Use `strategy_id` to retrieve the registered `StrategySignalHook`.
2.  **Schema Retrieval**: Obtain the `SignalFrameSchemaV1` for the given `strategy_version`.
3.  **Frame Enrichment**: Call `build_signal_frame` (via the factory) to transform the raw `bars` into a `signals_frame` containing indicators (ATR, etc.).
4.  **Validation**: Factory handles the contract validation.
5.  **Downstream Propagation**: Pass the enriched `signals_frame` into `generate_intent` as the primary data source.

---

## E) Evidence Pack

### 1. Verification of `signals_frame` creation
```text
$ rg -n "signals_frame = " src/axiom_bt/pipeline
src/axiom_bt/pipeline/signals.py:74:    signals_frame = pd.DataFrame(signals)
```

### 2. Indicator reference search (Strategy vs Pipeline)
```text
$ rg -n "atr|inside_bar|mother_high" src/axiom_bt src/strategies
src/strategies/inside_bar/signal_schema.py:28:        ColumnSpec("atr", "float64", False, "indicator"),
src/strategies/inside_bar/signal_schema.py:29:        ColumnSpec("inside_bar", "bool", False, "indicator"),
src/strategies/inside_bar/signal_schema.py:30:        ColumnSpec("mother_high", "float64", True, "indicator"),
src/axiom_bt/strategy_hooks/insidebar_intraday_hook.py:47:        df["atr"] = rng.bfill().fillna(0.0)
src/axiom_bt/strategy_hooks/insidebar_intraday_hook.py:51:        df["inside_bar"] = (df["high"] <= prev_high) & (df["low"] >= prev_low)
src/axiom_bt/strategy_hooks/insidebar_intraday_hook.py:52:        df["mother_high"] = prev_high
```
*Note: Indicators exist only in Strategy/Hook layers, not in Pipeline.*

### 3. Strategy Hook Registry call check
```text
$ rg -n "get_hook" src/axiom_bt/pipeline
src/axiom_bt/pipeline/signal_frame_factory.py:10:from axiom_bt.strategy_hooks.registry import get_hook
src/axiom_bt/pipeline/signal_frame_factory.py:40:    registry_get = hook_registry.get_hook if hook_registry else get_hook
```
*Note: Only the orphaned factory calls the registry.*

### 4. Orificing of `runner.py` (Missing Factory Call)
```text
$ rg -n "signal_frame_factory|build_signal_frame" src/axiom_bt/pipeline/runner.py
(No results)
```
