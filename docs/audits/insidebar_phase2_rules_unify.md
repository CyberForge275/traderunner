# InsideBar Phase 2 — Rules SSOT Unification (No Lookahead)

Date: 2026-02-05
Branch: refactor/insidebar-core-split-v1
Tag (rollback): insideBar_pre_phase2_rules_unify_v1

## What changed (scope-limited)
1) **SSOT rules module**
   - New: `src/strategies/inside_bar/rules.py`
   - Central rule evaluation:
     - `eval_vectorized(...)`
     - `eval_scalar(...)`
   - Supported modes:
     - `mb_body_oc__ib_hl`
     - `mb_body_oc__ib_body`
     - `mb_range_hl__ib_hl`

2) **Vectorized detection now uses SSOT**
   - `src/strategies/inside_bar/pattern_detection.py` now calls `rules.eval_vectorized(...)`.
   - No duplicate rule logic in this file anymore.

3) **Session arming uses SSOT flag only**
   - `src/strategies/inside_bar/session_logic.py` no longer re-implements InsideBar conditions.
   - It relies on `current["is_inside_bar"]` (computed by SSOT rules).

## Duplication removed
Previously, InsideBar condition was computed in:
- `pattern_detection.detect_inside_bars(...)`
- `session_logic.generate_signals(...)` (mother body rule re-check)

Now:
- **Only** `rules.eval_vectorized(...)` defines the InsideBar condition.
- `session_logic` consumes the SSOT result and only applies session/mother-same-session checks.

## Tests that prove parity / correctness
- `src/strategies/inside_bar/tests/test_rules.py`
  - per-mode positives/negatives
  - strict vs inclusive boundary
  - scalar vs vectorized parity
- `src/strategies/inside_bar/tests/test_core.py`
  - integration of detection + signal generation (updated datasets for mode #1)
- `src/strategies/inside_bar/tests/test_parity.py`
  - backtest adapter vs core parity

## SSOT Map
- **Rule definition:** `rules.eval_vectorized` / `rules.eval_scalar`
- **Vectorized detection:** `pattern_detection.detect_inside_bars -> rules.eval_vectorized`
- **Session arming:** `session_logic.generate_signals` uses `current["is_inside_bar"]`

## Lookahead / risk
No lookahead introduced:
- Rules use only current bar and previous (mother) bar data.
- No future bars, fills, or trade outcomes are used.

## Rollback
```
git checkout main
git reset --hard insideBar_pre_phase2_rules_unify_v1
```
