# AGENTS.md — Traderunner Multi-Repo Agent Contract (SSOT)
This file is the Source of Truth (SSOT) for AI agents and human contributors working on:
- traderunner/
- marketdata-stream/
- automatictrader-api/

If any instruction conflicts with other docs or code comments, THIS file wins unless explicitly stated otherwise.

---

## 0) Absolute First Step (MANDATORY)
Before touching code, the agent MUST read and follow these SSOT docs (in this repo):
- AI_CONTRIBUTION_GUIDE.md
- ENGINEERING_MANIFEST.md
- FACTORY_LABS_AND_STRATEGY_LIFECYCLE.md
- BACKTESTING_HANDOVER.md

If the agent cannot locate them, STOP and report that as a blocking issue.

---

## 1) Non-Negotiable Guardrails
### 1.1 Tests-First (always)
- Every behavioral fix starts with a RED regression test.
- Only then implement the fix → GREEN.
- No “quick fix” without a test unless change is **purely** comments/docs.

### 1.2 Minimal Diff Policy
- Smallest possible change to solve the problem.
- No drive-by refactors, no mass formatting, no unrelated cleanup.
- Changes must be deterministic and audit-friendly.

### 1.3 Layering / Ownership
- Business logic lives in `src/**` services/engine modules.
- UI callbacks/layout are thin wiring only.
- No business logic inside UI callbacks.

### 1.4 Data Source Segregation (CRITICAL)
- Backtest data source: Parquet/EODHD only.
- Live/Pre-Paper data source: SQLite only.
- Live/Pre-Paper MUST NEVER write to backtest Parquet.
- Backtest artifacts are write-once per run_dir.

### 1.5 Timezone Invariants (CRITICAL)
- Market timezone is immutable: `America/New_York`.
- Display timezone is presentation-only; never affects calculations.

### 1.6 Strategy Versioning / “Backtest Atom”
- Once a strategy version/profile is promoted, behavior is immutable.
- Any behavior change requires a version bump per lifecycle rules.
- Pre-Paper consumes SSOT manifests only (no ad-hoc config).

---

## 2) Backtest Pipeline SSOT Contract (must never break)
Every backtest run MUST create a run directory and these artifacts:

### 2.1 Artifact Directory SSOT
- The run is identified in UI and code by `run_dir` (directory name).
- `job_id` and `run_name` are labels only (never used for filesystem lookup).

### 2.2 Required Files (always)
In: `artifacts/backtests/<run_dir>/`
- `run_meta.json`  (written at start)
- `run_result.json` (written at end ALWAYS)
- `run_manifest.json` (written at end ALWAYS; SSOT for promotion)
Optional:
- `error_stacktrace.txt` (only on ERROR)
- `coverage_check.json` / `sla_results.json` (if present in design)
- `pipeline.log` (optional)
- `run_steps.jsonl` (preferred for UI steps)

### 2.3 Status Model (only these outcomes)
- `SUCCESS`
- `FAILED_PRECONDITION` with `FailureReason` + details
- `ERROR` with `error_id` + details
NO generic “Pipeline Exception” as a primary outcome in UI.

### 2.4 Gating (hard gates)
- Coverage Gate must be evaluated before strategy execution.
- SLA Gate must be evaluated before strategy execution.
- If gates fail: run_result = FAILED_PRECONDITION with reason and details; execution must not continue.

---

## 3) UI Contract (Dash) — Invariants that stop regressions
### 3.1 Single SSOT store for the active run
- `dcc.Store(id="bt-active-run")` holds:
  `{run_dir, run_id, run_name, job_id, started_at_utc}`
- Only the “Run Backtest” callback writes this store.
- Polling callbacks MUST NOT clear or overwrite it.

### 3.2 run_dir is the only lookup key
- All UI panels (summary, status, steps, logs, metrics) read `run_dir` from `bt-active-run`.
- No callback may construct expected paths from job_id or run_name.

### 3.3 No silent waiting
- If `run_dir` exists but required files are missing:
  after N polls (default 3) the UI must switch to a visible diagnostic state:
  show expected path + candidate dirs + missing files.
- Never endless “Waiting…” without reasons.

### 3.4 Status is derived only from run_result.json
- UI status must be parsed from `run_result.json`.
- Logs are not allowed to override status.

### 3.5 Logs and steps must be run-scoped
- “Raw logs / steps” panel must read ONLY from files within `run_dir`.
- No global “current_*.csv” or shared “last run wins” artifacts as UI sources.
- Legacy sources (e.g., legacy run_log.json) must be displayed only in a separate “Legacy Viewer” (if needed).

### 3.6 Polling is read-only
- Polling callbacks may update only view components (panels), never inputs or the SSOT store.

### 3.7 Callback determinism (no “magic” initial state)
- If a page/tab sets a default dropdown value, the details callback MUST render without user interaction.
- `prevent_initial_call=True` is forbidden for any callback that renders the primary details pane.
  - Exception: only if a separate “bootstrap” callback triggers the first render explicitly.

### 3.8 Inputs vs State (polling must not behave like a second user)
- Polling (`dcc.Interval`) should be **State** unless you explicitly want it to trigger recomputation.
- If polling is an **Input**, the callback MUST:
  - use `dash.callback_context.triggered_id` (or `dash.ctx.triggered_id`) to branch, and
  - avoid re-reading heavy artifacts unless the run is still in a non-terminal state.
- Terminal states: `SUCCESS`, `FAILED_PRECONDITION`, `ERROR` → stop expensive work (no repeated file reads).

### 3.9 Single writer rule (Outputs & stores)
- Each Output (including `dcc.Store`) must have exactly one callback writing it.
- No “helper” callbacks that silently overwrite the store or clear selection values.
- If a second update path is needed, refactor into one callback with multiple Inputs and explicit branching.

### 3.10 Callback-level tracing (TRACE-FIRST for UI)
Every callback that touches backtest state must log:
- `callback_name`, `run_id`, `run_dir`, `triggered_id`, `n_intervals` (if present)
- `exists()` checks for required artifacts:
  - `run_meta.json`, `run_result.json`, `run_manifest.json`, `run_steps.jsonl`
- Count + size of artifacts index (if present)
- Outcome: `rendered`, `no_update`, or `diagnostic_state`

### 3.11 Never silently drop data (empty UI must be explained)
- If steps/logs/metrics/charts are missing, the UI must render a diagnostic card:
  - which file is missing
  - where it was expected
  - whether the run is “signals-only” (no equity curve expected)
- Empty tables without explanation are forbidden.

### 3.12 Steps rendering contract (new pipeline)
- If `run_steps.jsonl` exists, the UI MUST display steps from it.
- If durations are not present, UI may:
  - display `—` for duration, or
  - compute duration by pairing `started`/`completed` timestamps per step.
- Legacy `run_log.json` may be supported only as a fallback and must be labeled “legacy”.

### 3.13 Error handling contract
- Callbacks must catch exceptions and:
  - log a full stacktrace server-side, and
  - render a user-visible error card containing:
    - error_id (if available)
    - run_id
    - the failing file/path
- Do NOT swallow exceptions and return placeholders.

### 3.14 Dash component IDs are immutable and unique
- Component `id`s are part of the public UI contract.
- Do not change IDs casually; if changed, update all callbacks + tests in the same PR.
- IDs must be globally unique within the app (no duplicates).
---

## 4) Debugging & Observability Rules
### 4.1 Debug Mode must be readable
- If a Debug panel exists, it must follow contrast/accessibility:
  high-contrast text; avoid low-contrast yellow/grey combinations.

### 4.2 Debug Mode is non-invasive
- Debug Mode may display internal values but must not alter behavior.

### 4.3 Always attach evidence in PR
- At minimum: paths to artifacts + relevant snippets of run_result/run_manifest + logs (short).
- For UI fixes: screenshots before/after.

---

## 5) Golden Tests / Promotion Gate
- In Lab/INT: golden tests may SKIP if data missing.
- For promotion to Pre-Paper or beyond:
  `REQUIRE_GOLDEN_DATA=1` must be enabled and SKIPs become FAIL with a clear message:
  “Golden data missing (promotion blocked).”

---

## 6) Standard Work Protocol (how an agent must work)
1) Read SSOT docs (Section 0).
2) Reproduce the issue (local or INT) and collect evidence.
3) Write a RED regression test that reproduces the issue.
4) Implement minimal fix to go GREEN.
5) Run the smallest relevant test suite locally (then full suite if risk).
6) Provide a short audit report:
   - Problem / Evidence / Fix / Invariants preserved / Tests added / Remaining risks
7) Only then deploy (if requested) and run manual smoke checks.

---

## 7) Canonical Commands (update if repo changes)
> If a command fails due to missing tooling, report that as a finding and propose a single canonical alternative.

### traderunner
- Tests (core backtest + UI integration):
  `PYTHONPATH=src:. pytest -q`
- Single file:
  `PYTHONPATH=src:. pytest -q tests/test_<name>.py -q`

### marketdata-stream
- Tests (preferred, if src layout exists):
  `PYTHONPATH=src:. pytest -q`

### automatictrader-api
- Tests (preferred, if src layout exists):
  `PYTHONPATH=src:. pytest -q`

### INT service checks (if deployed with systemd)
- Logs:
  `sudo journalctl -u trading-dashboard-v2 -n 200 --no-pager`
- Restart:
  `sudo systemctl restart trading-dashboard-v2 && sudo systemctl status trading-dashboard-v2 --no-pager`

### Artifacts discovery
- Latest runs:
  `ls -lt /opt/trading/traderunner/artifacts/backtests | head -n 20`

---

## 8) PR Template (must be included in every PR description)
- Problem:
- Evidence (paths/logs/screenshots):
- Root cause:
- Fix (minimal diff):
- Invariants checked (list):
- Tests added (RED→GREEN):
- Manual verification steps:
- Rollback plan:

---

## 9) “Stop Conditions” (agent must stop and report)
Stop immediately if any of these occur:
- A fix would require relaxing guardrails (data mixing, layering violations, TZ changes).
- The issue cannot be reproduced and no reliable instrumentation exists.
- The agent is about to make broad refactors unrelated to the bug.
- Required SSOT docs are missing.

## 10) Mandatory Pre-Fix Automation (Agent MUST run these)
Goal: Prevent “blind fixes” and long debugging loops. Every bugfix PR must include:
- evidence, reproducibility, regression test, minimal diff, and explicit invariant checks.

### 10.1 Pre-flight: identify current integration path (UI → pipeline)
Before changing code, the agent MUST prove which code path is active.

Run (from repo root):
- `git status --porcelain`
- `git rev-parse --short HEAD`
- `git grep -n -E "signals\.cli_inside_bar|Pipeline Exception|run_log\.json|current_signals" -- . || true`
- `git grep -n -E "run_result\.json|run_manifest\.json|bt-active-run|run_dir" -- . || true`

PR must include a short “Integration Path Evidence” section:
- which callback/file triggers the run
- which function is invoked (new pipeline vs legacy)
- which artifacts are used for UI rendering

### 10.2 Canonical minimal reproduction checklist (must be captured)
For every bug, capture these in the PR description (copy/paste):
- Environment: OS, Python, commit SHA, branch
- Repro steps: 3–5 steps
- Expected vs actual
- Evidence: exact file paths + 1–3 snippet lines

For backtest/UI bugs, evidence MUST include:
- `artifacts/backtests/<run_dir>/run_meta.json`
- `artifacts/backtests/<run_dir>/run_result.json`
- `artifacts/backtests/<run_dir>/run_manifest.json` (if present)
- and the UI mapping values:
  `run_dir`, `run_name`, `job_id`, `expected_dir`

### 10.3 Regression test requirement (RED → GREEN)
Every behavioral fix must be preceded by a failing test that reproduces the bug.
PR must show:
- Test name(s)
- Why the test is sufficient (1–2 sentences)
- Proof of RED→GREEN (test output snippet or summary)

### 10.4 Mandatory invariant checks (must be explicitly listed)
Agent MUST include a checklist in the PR description (checked items):
- [ ] No data source mixing (backtest parquet vs live/pre-paper sqlite)
- [ ] Market TZ remains America/New_York
- [ ] No business logic in UI callbacks (thin wiring only)
- [ ] run_dir is the only lookup key; job_id never used for filesystem lookup
- [ ] Polling callbacks are read-only; do not reset inputs or stores
- [ ] Status derived only from run_result.json (not logs)
- [ ] Artifacts always created: run_meta at start; run_result+run_manifest at end
- [ ] Golden skip policy preserved (REQUIRE_GOLDEN_DATA=1 blocks promotion)

### 10.5 Mandatory test commands (must run and report)
At minimum, the agent MUST run:
- Focused tests for changed area (explicit list)
- plus one “core suite” command

Traderunner core:
- `PYTHONPATH=src:. pytest -q`

If repo has multiple suites, the agent must document which one is canonical and why.

### 10.6 Evidence capture (PR must include these snippets)
Backtest/UI fixes must include short snippets (do not paste full files):
- run_result.json: status + reason/error_id + key details
- run_manifest.json: identity.strategy.data keys (short)
- One screenshot or log excerpt showing correct UI binding to run_dir

### 10.7 Stop Conditions (hard)
If any of the following is true, STOP and report instead of changing code:
- Fix would relax guardrails or mix data sources
- Bug cannot be reproduced and no deterministic instrumentation exists
- Proposed change is large refactor without regression test
- Multiple competing SSOTs exist (must consolidate first)

## 11) UI Contract Addendum — Dash Callbacks (Regression Guardrails)

> Goal: Prevent “works after click”, empty panes, missing charts, and silent failures.

### 11.1 Deterministic Initial Render (No “click to load”)
- When the user opens the Backtests tab, the Details/Result pane MUST render deterministically:
  - If a latest run exists, it MUST be auto-selected and rendered.
  - No UI state may require a manual dropdown click to trigger rendering.
- Allowed triggers for initial render:
  - `dcc.Location(pathname)` OR active tab Input.
- Avoid `prevent_initial_call=True` on critical “render details” callbacks unless a documented alternative trigger exists.

### 11.2 Single SSOT for Selection (run_dir)
- The selected run MUST be represented by exactly one SSOT store:
  - `dcc.Store(id="bt-active-run")` containing at least `{run_dir, run_id, started_at_utc}`.
- All detail panels MUST read from `run_dir` only.
- Never use `job_id` or `run_name` for filesystem lookup.

### 11.3 Callback Input/State Rules
- If a value changes what is rendered, it MUST be an `Input`, not only `State`.
- `State` is allowed only for non-triggering auxiliary values.
- Every callback MUST handle `None` safely:
  - Return a visible “Select a run” message, not empty tables.

### 11.4 Artifact Reading Contract (UI)
- UI details MUST be sourced from artifact files inside `run_dir` only:
  - Meta: `run_manifest.json` (preferred) else `run_meta.json`
  - Status: `run_result.json` only
  - Steps: `run_steps.jsonl` (preferred) (or documented alternative)
  - Charts/Metrics: only if the underlying artifact files exist
- If a required artifact is missing:
  - UI MUST show a clear diagnostic (“missing <file> in <run_dir>”) and MUST NOT silently show zeros.

### 11.5 Steps/Logs Rendering (TRACE-FIRST)
- The “Steps / Performance” panel MUST render something if `run_steps.jsonl` exists:
  - At minimum: step_name + status + timestamp
  - Prefer: compute duration from `started`/`completed` pairs
- “Raw logs” MUST be run-scoped:
  - No global “current_*” shared files.

### 11.6 Charts Panel Rules
- Charts MUST be derived from artifacts (equity_curve, trades, orders, metrics).
- If the current pipeline is “signals-only” and does not produce trading artifacts:
  - The UI MUST explicitly label it (“Signals run”) and hide/disable trading charts OR show a clear “not available” message.
- Never render a “success” run with empty charts without explanation.

### 11.7 No Duplicate Component IDs / Accessibility
- UI MUST NOT create duplicate HTML `id` attributes (browser console warnings are treated as defects).
- Every form control should have a stable id/name and a label association where feasible.
- Duplicate ids are a STOP issue for UI changes.

### 11.8 Fail Fast, Visible, and Logged (UI)
- Callback exceptions MUST NOT fail silently.
- On error:
  - Log server-side with `{run_dir, callback_name, exception}`
  - Render a visible error panel with a short error_id and where to find logs.

### 11.9 Debug Mode (UI)
- If `DASH_UI_DEBUG=1`:
  - Show a “Discovery/Details Debug” panel:
    - selected run_dir
    - files found/missing
    - parse errors
    - rows returned for steps/logs/tables
- Debug mode must be readable (high contrast) and must not change behavior.

### 11.10 UI Regression Tests (Minimum Set)
- Add/maintain tests that guarantee:
  - Latest run is rendered on initial page/tab load (no click required)
  - A run with `run_meta.json` + `run_result.json` + `run_steps.jsonl` renders non-empty steps
  - Missing chart artifacts produce a visible “missing artifacts” message (not silent zeros)
