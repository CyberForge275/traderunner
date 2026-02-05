# InsideBar Rule Modes — Implementation Plan (SSOT, Modular, Rollback‑Safe)

## A) Preconditions / Safety
- `git status -sb` (before work): showed dirty state due to an existing untracked doc `docs/audits/insidebar_mb_ib_mode_switch_plan.md`.
- Rollback anchor confirmed: tag `insideBar_v0.8` exists.
- HEAD: `39eb628ff2ee4809f020af48d3702d1619ce89e3`
- `git describe --tags --always`: `insideBar_v0.8-1-g39eb628`
- Branch created: `feat/insidebar-rule-modes`

**Note:** This is plan-only. No code changes performed.

## B) Current Behavior (live rule + usage points)
**Rule currently live:**
- InsideBar uses **mother body** and requires `ib_high` and `ib_low` inside the body (inclusive/strict via `inside_bar_mode`).

**Where it’s applied (duplicated today):**
1) Vectorized mask:
   - `src/strategies/inside_bar/core.py::detect_inside_bars` (approx L183–263)
   - Builds `inside_mask` and sets `is_inside_bar`.
2) Session state machine gate (per-row):
   - `src/strategies/inside_bar/core.py` inside `if not state['armed']` (approx L428–495)
   - Recomputes `is_inside` again.

**Risk:** duplicated logic can drift; single SSOT rule is required.

## C) Mode Switch — Canonical Set of 4 Modes
Introduce config field: `inside_bar_definition_mode` with allowed values:

1) `mb_body_oc__ib_hl`
   - **IB full candle** (high/low) within **MB body** (open/close)
   - Condition: `ib_high <= mb_body_high AND ib_low >= mb_body_low`

2) `mb_body_oc__ib_body`
   - **IB body** (open/close) within **MB body** (open/close)
   - Condition: `ib_body_high <= mb_body_high AND ib_body_low >= mb_body_low`

3) `mb_range_hl__ib_hl`
   - **IB full candle** within **MB range** (high/low)
   - Condition: `ib_high <= mb_high AND ib_low >= mb_low`

4) `mb_body_oc__ib_hl_v2`
   - **Alias of mode_1** (as required). Documented explicitly as alias.
   - If later diverges, this alias becomes its own formula.

**Strict vs inclusive** remains controlled by `inside_bar_mode`:
- inclusive: `<=` / `>=`
- strict: `<` / `>`

Edge cases to document:
- Doji mother (open == close): body range = 0 → strict nearly always false.
- Timestamp alignment irrelevant to rule; rule uses OHLC only.

## D) Architecture (SSOT Rule — No Drift)
**New module:** `src/strategies/inside_bar/insidebar_rules.py`

Responsibilities:
- `bounds_body(open, close) -> (low, high)`
- `bounds_range(high, low) -> (low, high)`
- `eval_inside_bar_scalar(mb_ohlc, ib_ohlc, mode, strict) -> bool`
- `eval_inside_bar_vectorized(df, mode, strict) -> pd.Series[bool]`
- `ALIAS_MAP` to map `mb_body_oc__ib_hl_v2` → `mb_body_oc__ib_hl`

**core.py usage plan:**
- `detect_inside_bars` uses `eval_inside_bar_vectorized`
- State machine uses **either**:
  - the already computed `is_inside_bar` flag for that row, or
  - `eval_inside_bar_scalar` for the exact two bars

This guarantees **single-source rule**.

## E) Config + Spec Integration (Plan only)
**Config field:** `inside_bar_definition_mode: str`
- Location: `src/strategies/inside_bar/config.py`
- Default must be **backward compatible** (legacy mode).

**Spec validation:** `src/strategies/config/specs/inside_bar_spec.py`
- Validate allowed strings and alias handling
- Error message must list allowed modes

**YAML integration (later):**
- `insidebar_intraday.yaml` to set new mode explicitly
- Not in this plan step; only after GO.

## F) Test Plan (Matrix per Mode)
Create new tests under:
- `src/strategies/inside_bar/tests/test_insidebar_rules.py`

For each mode, test:
- Positive case (True)
- Negative case (False)
- Boundary case for strict vs inclusive

Extra cases:
- Mother doji (open == close)
- IB high/low equals boundary
- Vectorized vs scalar parity test (same input ⇒ same result)

## G) Audit / Trace Plan
**Debug fields (optional, no behavior change):**
- `dbg_mb_body_low`, `dbg_mb_body_high`
- `dbg_ib_body_low`, `dbg_ib_body_high`
- `dbg_inside_rule_mode`

**Logging (actions: prefix):**
- `actions: insidebar_rule_mode mode=<...> strict=<...>`
- `actions: insidebar_rule_eval ib_ts=<...> result=<...>`

## H) Rollback / Release Plan
- Rollback tag: `insideBar_v0.8`
- Rollback command:
  ```
  git checkout main
  git reset --hard insideBar_v0.8
  ```

## I) GO‑Sequence (Patch plan if approved)
- Patch‑0: add `insidebar_rules.py` + tests (no behavior change)
- Patch‑1: refactor `core.py` to use SSOT rules
- Patch‑2: config/spec updates (mode string validation + default)
- Patch‑3: optional YAML default change (if explicitly requested)

## Status
No code changes performed in this step. This is plan‑only.
