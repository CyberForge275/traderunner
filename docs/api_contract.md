# API Contract (Business + Compatibility)

Contract scope is limited to two public interfaces:
1) marketdata uvicorn HTTP API (`marketdata-monorepo/src/app.py`)
2) traderunner batch/CLI pipeline API (`traderunner/src/axiom_bt/pipeline/cli.py` + `runner.py`)

This is a freeze document for compatibility and change management.

## 1) Contract Scope

### Public API

- HTTP endpoints:
  - `POST /ensure_bars`
  - `POST /ensure_timeframe_bars`
- Pipeline invocation surfaces:
  - CLI: `python -m axiom_bt.pipeline.cli ...`
  - UI adapter path: `trading_dashboard/services/new_pipeline_adapter.py -> run_pipeline(...)`
- Pipeline artifacts consumed by UI/tools:
  - `run_meta.json`, `run_result.json`, `run_manifest.json`
  - `signals_frame.csv`, `events_intent.csv`, `fills.csv`, `trades.csv`, `equity_curve.csv`, `portfolio_ledger.csv`, `metrics.json`

### Internal (non-public)

- Internal helper modules and pure functions under `src/**` that are not directly invoked by external callers
- Implementation details of indicator math and low-level helper functions

## 2) Invariants / Semantics

### 2.1 Time and session semantics

- Session mode is explicit (`rth` or `raw`), passed in request/config.
- Session timezone is explicit (`session_timezone`).
- For marketdata service:
  - `raw` => no session-window filter
  - `rth` => effective window resolved from service SSOT config (`session_windows.yaml`)
- `effective_session_window` is part of `/ensure_timeframe_bars` response details for audit.

### 2.2 Determinism

- Same data inputs + same strategy version + same resolved config => same pipeline outputs (artifact content), except additive metadata fields.
- Run identity for filesystem lookup is `run_dir`; labels (`run_name`, `job_id`) are not filesystem keys.

### 2.3 Strategy lifecycle

- Finalized strategy versions are immutable.
- Behavioral changes require new strategy version opt-in.

### 2.4 Costs/slippage semantics

- Costs are resolved via config resolver and must be present as `commission_bps` and `slippage_bps` in resolved config.
- Manifest must include resolved config + sources for auditability.

## 3) Backward Compatibility Rules

### 3.1 Breaking changes (forbidden without contract/version bump)

- Removing or renaming existing HTTP endpoints.
- Removing/renaming existing request/response fields.
- Type changes for existing fields.
- Changing artifact filenames.
- Changing semantic meaning of existing artifact columns.
- Silent default changes that alter strategy or execution behavior.

### 3.2 Non-breaking changes (allowed)

- Additive optional response fields.
- Additive CSV columns.
- New optional endpoints.
- New strategy versions (opt-in) with unchanged old versions.

### 3.3 Deprecation workflow

1) Mark as deprecated in docs + runtime warning (where applicable).
2) Keep dual support for at least one release cycle.
3) Remove only in major contract revision with migration note.

## 4) Contract Tests (CI gates)

### 4.1 HTTP contract tests

Minimum tests:
- Endpoint availability and method correctness for `/ensure_bars` and `/ensure_timeframe_bars`.
- Request validation behavior (required fields, range checks).
- Response envelope contains stable fields (`status`, `gaps_before`, `gaps_after`, `details`).
- For `session_mode=rth`, assert `details.effective_session_window` is present and stable.

Optional:
- OpenAPI snapshot generation + diff in CI.

### 4.2 Pipeline contract tests

Minimum tests:
- Pipeline writes mandatory artifacts to run directory.
- `run_manifest.json` and `run_result.json` always written on terminal run paths.
- Required CSV artifact files exist and are parseable.
- Additive-only schema evolution: required baseline columns remain.

### 4.3 Consumer-driven checks

- UI consumers validate only contract surfaces (`run_dir`, artifact names, stable status/result fields).
- Avoid binding tests to internal implementation details.

## 5) Change Management

### 5.1 Proposal workflow

Any contract-surface change must include:
- ADR/decision note
- explicit contract version bump in docs
- migration notes for consumers

### 5.2 Release checklist

- Update `docs/api.md` and `docs/api_contract.md`
- Update/add contract tests
- Provide evidence snippets:
  - HTTP request/response example
  - `run_result.json` status snippet
  - `run_manifest.json` config snippet

## 6) Current Known Contract Risks (to track)

1) CLI currently maps missing `--fees-bps/--slippage-bps` to `0.0` at call-site while base YAML provides non-zero defaults; this can cause semantic drift between invocation paths.
2) `/ensure_bars` request contains `session_mode/session_timezone` but current coverage call path does not use them directly.
3) Status casing differs by layer (`success` in runner result payload vs uppercase enums used by some legacy services/docs).

These are documented for visibility; this file does not change runtime behavior.
