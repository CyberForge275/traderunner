# Configuration Pane Analysis

> **📜 HISTORICAL DOCUMENT**
> **Date**: November 2025
> **Context**: Streamlit UI refactoring analysis

## Iteration 1 – Scope & Flow Mapping

### Objective
Understand the current sidebar structure and how user inputs propagate through the pipeline.

### Findings
- Sidebar is a monolithic block inside `app.py` mixing UI controls, validation, and CLI orchestration.
- Timeframe, symbol inputs, YAML/manual modes, and pipeline commands are interleaved.
- Input data is converted ad-hoc into fetch arguments without explicit validation helpers.

### Risks / Limitations
- Hard to extend with new strategies or additional parameters without touching large blocks of code.
- Minimal separation between configuration state and side effects (CLI invocations).

### Improvement Opportunities
1. Extract configuration data into structured objects (e.g., dataclasses or dictionaries) before running steps.
2. Introduce helper functions to sanitize/validate symbol lists and date ranges.
3. Prepare for multi-strategy support by isolating strategy-specific defaults.

---

## Iteration 2 – Input Validation & UX Review

### Objective
Assess robustness of user input handling and identify UX friction points.

### Findings
- Symbols: free-form text area merged with cached selection but no validation beyond non-empty check.
- Date handling: conversions rely on `pd.Timestamp`; no feedback for invalid ranges (start > end).
- YAML mode: displays payload but does not guard against syntactic errors or missing keys before backtest run.
- “Use synthetic data” default corrected, but UI lacks hints when internet/API token is required.

### Risks / Limitations
- Erroneous inputs surface as CLI exceptions after long-running steps, leading to poor UX.
- Manual mode may trigger fetch without confirming target files/directories exist.

### Improvement Opportunities
1. Add explicit validation functions with user-friendly error messages before running CLI steps.
2. Provide contextual help/tooltips for API token requirements and data availability.
3. Introduce status summaries of pending operations (e.g., “Fetching 2 symbols, dates …”).
4. Cache previous configurations so users can quickly rerun with minor tweaks.

---

## Iteration 3 – Code Structure & Extensibility

### Objective
Examine maintainability and readiness for new strategies/features.

### Findings
- `app.py` encapsulates both UI definitions and orchestration logic; no modular separation.
- Strategy settings are hardcoded (e.g., sessions, CLI arguments) within sidebar button handler.
- Adding new strategies would require editing multiple sections (symbol parsing, CLI arguments, config payload).
- No plug-in architecture for fetching additional data types (e.g., different timeframes or providers).

### Risks / Limitations
- High coupling makes regression risk substantial when expanding features.
- Strategy-specific logic may proliferate, making the file unwieldy.

### Improvement Opportunities
1. Extract pipeline orchestration into dedicated module/class with methods like `ensure_intraday`, `generate_signals`, etc.
2. Define configuration schemas per strategy to drive UI generation dynamically.
3. Implement registry for strategies exposing metadata (required inputs, default sessions, CLI modules).
4. Allow injection of data providers to accommodate different APIs or offline datasets.

---

## Iteration 4 – Roadmap & Action Plan

### Objective
Synthesize improvements into actionable steps prioritizing quality, stability, and future extensibility.

### Recommendations
1. **Modularize Configuration Logic**
   - Create a `ui/configurator.py` (or similar) responsible for building sidebar state objects.
   - Introduce dataclasses representing `RunConfig`, `FetchConfig`, and `StrategyConfig`.

2. **Centralize Validation**
   - Implement reusable validators returning `(is_valid, message)` for symbols, dates, YAML payloads.
   - Surface validation results before executing CLI subprocesses.

3. **Strategy Registry & Metadata**
   - Extend existing `strategies.registry` to expose UI metadata (name, supported timeframes, default sessions).
   - Drive UI options dynamically from registry to simplify adding new strategies.

4. **User Feedback Enhancements**
   - Provide pre-flight summary (symbols, date range, strategy) before launch.
   - Persist recent configurations in Streamlit session state for quick reruns.

5. **Testing & CI**
   - Add unit tests for new validation/helpers.
   - Consider snapshot/regression tests for Streamlit layout using `pytest` plugins or integration tests.

### Next Actions
- Prioritize refactoring (`ui/configurator.py`, validation helpers) to reduce coupling.
- Implement registry-driven options enabling strategy extensibility.
- Expand automated tests to cover new logic and prevent regressions.

---
