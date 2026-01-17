# Forensic Audit: Pipeline Strategy Signal Frame Attachment

- **Audit Date**: 2026-01-14
- **Auditor**: Antigravity (Forensic Code Auditor)
- **Status**: Complete (Read-Only)

---

## A) Current State Summary

1.  **Attachment Mechanism**: The pipeline currently does **not** attach strategy-specific columns at runtime using the intended `SignalFrameFactory`. Instead, it uses a **mock logic** located in `src/axiom_bt/pipeline/signals.py` that generates a local `signals_frame`.
2.  **Missing Strategy Integration**: The `StrategyHook` system (specifically `InsideBarSignalHook`) is dormant and disconnected from the `run_pipeline` orchestrator.
3.  **Proof Flaw**: The system relies on the **persisted** `signals_frame.parquet` as proof of signal generation. This frame currently contains only mock data and lacks real strategy indicators (ATR, etc.).
4.  **Schema Drift**: Several files outside the `src/strategies/**` package define or assume signal column structures, violating the principle of strategy-owned schemas.

---

## B) Call Graph (Modular Pipeline)

The following call chain occurs in `src/axiom_bt/pipeline/runner.py`.

| Step | File | Function | Line Range | Data Impact |
| :--- | :--- | :--- | :--- | :--- |
| **0** | `runner.py` | `run_pipeline` | 25-196 | Entry point / Orchestrator |
| **1** | `data_prep.py` | `load_bars_snapshot` | 124 | Returns `(bars, bars_hash)` |
| **2** | **MISSED** | `signal_frame_factory.py` | - | **ORPHANED**: Not called by runner. |
| **3** | `signals.py` | `generate_intent` | 126 | **MOCK**: Returns `IntentArtifacts` |
| **4** | `fill_model.py` | `generate_fills` | 127 | Matches intents to OHLCV |
| **5** | `execution.py` | `execute` | 129 | Applies sizing and builds trades |
| **6** | `metrics.py` | `compute_and_write_metrics` | 136 | Writes `metrics.json` |
| **7** | `artifacts.py` | `write_artifacts` | 176 | **PERSISTENCE**: Writes `signals_frame.parquet` |

---

## C) Runtime Signal Frame Attachment Points

1.  **Current (Mock)**: `src/axiom_bt/pipeline/signals.py::generate_intent`
    - Creates a local `signals_frame` (L74).
    - Hardcodes columns: `prev_close`, `side`, `symbol`.
2.  **Intended (Strategy Hook)**: `src/axiom_bt/strategy_hooks/insidebar_intraday_hook.py::extend_signal_frame`
    - Logic for `atr`, `inside_bar`, `mother_high`, `breakout_long` (L45-L57).
    - Status: Dormant.
3.  **Intended (Factory)**: `src/axiom_bt/pipeline/signal_frame_factory.py::build_signal_frame`
    - Status: Dormant.

---

## D) Schema Ownership Audit (Offenders List)

| File Path | Line Range | Violation Type | Description |
| :--- | :--- | :--- | :--- |
| `src/axiom_bt/contracts/signal_schema.py` | 95-107 | **Drift** | Defines `SIGNAL_COLUMNS` as a generic constant. |
| `src/axiom_bt/contracts/signal_schema.py` | 43 | **Drift** | Mentions `inside_bar` in `SignalOutputSpec` setup type. |
| `src/axiom_bt/strategy_hooks/insidebar_intraday_hook.py` | 45-78 | **Logic Drift** | Implements signal logic (ATR/InsideBar) outside `src/strategies/`. |
| `src/axiom_bt/pipeline/signals.py` | 52-72 | **Hardcoding** | Implements signal logic for intents locally. |

---

## E) Persisted Proof Audit

- **Writer**: `src/axiom_bt/pipeline/artifacts.py::write_artifacts` (L43).
- **Artifact Index**: `runner.py:L157` lists `signals_frame.parquet`.
- **UI Dependency**: No direct reading of `signals_frame.parquet` found in `trading_dashboard` (read via `bars_signal_*.parquet` in some legacy paths).
- **Status**: The existence of `signals_frame.parquet` as the primary signal artifact is the **wrong proof model**.

---

## F) Correct Proof Model (Runtime-only) — Gap Analysis

| Item | Status | Insertion Point / Gap |
| :--- | :--- | :--- |
| **Runtime Validation** | NO | Missing call to `validate_signal_frame_v1` in `runner.py`. |
| **Manifest Signature** | NO | `run_manifest.json` only stores data hashes, not schema signatures. |
| **Deterministic Logs** | PARTIAL | `actions: pipeline_completed` exists but lacks schema proof. |

**Insertion Point Needed**:
- `src/axiom_bt/pipeline/runner.py:L125`: `signals_frame = build_signal_frame(bars, strategy_id, ...)`
- `src/axiom_bt/pipeline/runner.py:L151`: Inject `schema_fingerprint` into `manifest_fields`.

---

## G) Strategy Versioning Requirement

### Current Structure:
- `src/strategies/inside_bar/signal_schema.py`: Single file containing versioned schemas in a dict.

### Target Architecture (Prototyped):
To achieve strict versioning and isolation, the strategy package should evolve to:
```text
src/strategies/inside_bar/
├── schemas/
│   ├── __init__.py
│   ├── common.py
│   ├── v1_0_0.py (schema + builder/builder call)
│   └── v1_1_0.py
├── versions/
│   ├── v1.00.yaml
│   └── v1.10.yaml
└── signal_schema.py (Dispatcher)
```

---

## H) Concrete Evidence Pack

### rg Evidence: Schema Drift
```text
src/axiom_bt/contracts/signal_schema.py:43:    setup: Optional[str] = Field(None, description="Setup type (e.g., 'inside_bar', 'breakout')")
src/axiom_bt/contracts/signal_schema.py:95:SIGNAL_COLUMNS = [
```

### rg Evidence: Implementation Drift (Hooks)
```text
src/axiom_bt/strategy_hooks/insidebar_intraday_hook.py:51:        df["inside_bar"] = (df["high"] <= prev_high) & (df["low"] >= prev_low)
src/axiom_bt/strategy_hooks/insidebar_intraday_hook.py:47:        df["atr"] = rng.bfill().fillna(0.0)
```

### rg Evidence: Persisted Proof Persistence
```text
src/axiom_bt/pipeline/artifacts.py:43:    write_frame(signals_frame, out_dir / "signals_frame.parquet")
src/axiom_bt/pipeline/runner.py:157:            "signals_frame.parquet",
```
