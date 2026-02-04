# Lookahead Intent Audit

## 1) Executive Summary
- **Scope:** `events_intent.csv` generation and persistence for insidebar pipeline runs.
- **Runs analyzed:**
  - `260202_090827__HOOD_IB_maxLossPCT001_300d`
  - `260202_090625_HOOD_IB_maxLossPct0_300d`
  - `260203_221225_HOOD_IB_allign2golden_300d` (selected as recent “golden-aligned” run)
- **Finding:** `events_intent.csv` contains **future-scheduled timestamps** (`exit_ts`, `dbg_valid_to_ts_*`, `dbg_exit_ts_ny`) for **all intents**, derived from session window policy in `signals.generate_intent`. This is deterministic and policy-driven, but it is **future information** relative to signal time.
- **No direct fill/trade leak** found in `events_intent.csv` (no `fill_price`, `realized_pnl`, etc.).
- **Risk rating:** **Moderate** — depends on whether “intent time” definition allows deterministic, policy-based future timestamps. If *any* future timestamps in intents are forbidden, this is a policy violation. If policy allows scheduled exit windows, this is acceptable but must be explicitly documented.

## 2) Definitions
- **Intent time:** end of the signal bar (inside bar detection time) when `events_intent` is generated.
- **Allowed at intent time:** fields computed from bars up to signal bar, strategy params, or session policy.
- **Forbidden at intent time:** values that depend on *future market evolution* (fills, realized PnL, exit triggered by price movement, etc.).

## 3) Observed Intent Schema
See: `docs/audits/intent_schema_inventory.csv`

Example (from `260202_090827__HOOD_IB_maxLossPCT001_300d`):
```
['template_id','signal_ts','symbol','side','entry_price','stop_price','take_profit_price','exit_ts','exit_reason',
 'strategy_id','strategy_version','breakout_confirmation','dbg_signal_ts_ny','dbg_signal_ts_berlin',
 'dbg_effective_valid_from_policy','dbg_valid_to_ts_utc','dbg_valid_to_ts_ny','dbg_valid_to_ts','dbg_exit_ts_ny',
 'dbg_valid_from_ts_utc','dbg_valid_from_ts','dbg_valid_from_ts_ny','sig_atr','sig_inside_bar','sig_mother_high',
 'sig_mother_low','sig_entry_price','sig_stop_price','sig_take_profit_price','sig_mother_ts','sig_inside_ts',
 'dbg_breakout_level','dbg_mother_high','dbg_mother_low','dbg_mother_ts','dbg_inside_ts','dbg_trigger_ts',
 'dbg_order_expired','dbg_order_expire_reason','dbg_mother_range']
```

## 4) Forbidden Fields Findings (per run)
See: `docs/audits/lookahead_scan_<runid>.md`

All three runs show **non-null**:
- `exit_ts` (session_end)
- `exit_reason` (session_end)
- `dbg_valid_to_ts_*` and `dbg_exit_ts_ny`
- `dbg_trigger_ts`

These are scheduled timestamps, not fill outcomes, but they are **future-dated** relative to signal time.

## 5) Intent Creation & Write Path (code evidence)
- **Producer:** `generate_intent(...)` in `src/axiom_bt/pipeline/signals.py:63-176`.
  - Sets `exit_ts`/`exit_reason` when `order_validity_policy == "session_end"` (`signals.py:118-129`).
  - Sets `dbg_valid_to_*` and `dbg_exit_ts_ny` at the same time.
  - Sets `dbg_trigger_ts` from `sig["trigger_ts"]` or falls back to `signal_ts` (`signals.py:161-164`).
- **Writer:** `write_artifacts(...)` in `src/axiom_bt/pipeline/artifacts.py:28-45` writes `events_intent.csv`.
- **Pipeline wiring:** `src/axiom_bt/pipeline/runner.py:190-224` calls `generate_intent`, then `generate_fills` and `execute`.

See: `docs/audits/intent_write_path.md`

## 6) Mutation Analysis (post-generation)
- `events_intent` is **not** mutated after `generate_intent`. It is passed to fills/execution read-only.
- `execution._build_trades` copies `events_intent` (`execution.py:90-107`) and mutates the copy only.

See: `docs/audits/intent_mutation_map.md`

## 7) Dependency Map (time-of-knowledge)
See:
- `docs/audits/intent_dependency_map.md`
- `docs/audits/intent_dependency_map.csv`

Highlights:
- **Signal-time fields:** `entry_price`, `stop_price`, `take_profit_price`, `signal_ts`, `template_id`, `side`, `sig_*`, `dbg_mother_*`, `dbg_inside_ts`, `dbg_breakout_level` (derived from signal frame + params).
- **Scheduled future fields:** `exit_ts`, `exit_reason`, `dbg_valid_to_ts_*`, `dbg_exit_ts_ny` (set by session policy at signal time).
- **Potential risk field:** `dbg_trigger_ts` (strategy-defined; insidebar sets it to signal timestamp, but could be future if strategy uses post-signal data).

## 8) Case Studies (rows)
See: `docs/audits/intent_row_case_studies.md`

Each case links `events_intent` with matching fills/trades by `template_id`, illustrating which fields are already present at intent time.

## 9) Conclusion / Risk
- **Lookahead present:** **No direct leak of fill/trade outcomes** observed in `events_intent.csv`.
- **Policy risk:** `exit_ts` + `dbg_valid_to_*` are future timestamps embedded at signal time. If your SSOT prohibits *any* future time data in intents, this is a **policy violation**. If session-end validity is allowed to be precomputed, then this is **acceptable** but should be explicitly documented in the intent contract.

## 10) Minimal remediation suggestions (no code)
- Clarify intent contract: are scheduled session-end timestamps allowed at intent time?
- If not allowed, move `exit_ts` / `dbg_valid_to_*` to a separate artifact (or fill layer) and keep intents “present-time only”.
- Keep `dbg_trigger_ts` semantics explicitly defined: signal time vs trigger time.

## Commands used
- `rg -n "events_intent|intent" src/axiom_bt/pipeline -S`
- `nl -ba src/axiom_bt/pipeline/signals.py | sed -n '63,190p'`
- `nl -ba src/axiom_bt/pipeline/runner.py | sed -n '160,260p'`
- `nl -ba src/axiom_bt/pipeline/execution.py | sed -n '90,200p'`
- `python scripts/audit/intent_audit_extract.py`
- `python scripts/audit/intent_case_studies.py`
- `python scripts/audit/intent_dependency_map.py`
