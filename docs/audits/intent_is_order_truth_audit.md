# Intent Is Order Truth – Audit Report

## Executive Summary
- **Finding:** Fills/trades are derived from `events_intent.csv` and keyed by `template_id`; no evidence of fills/trades without intent in the sampled runs. (See: `docs/audits/intent_fill_trade_join_keys.md`)
- **Finding:** InsideBar generates **one side per setup** (BUY **or** SELL), not OCO. Side is fixed at signal time. (Core: `src/strategies/inside_bar/core.py` L535–L717)
- **Finding:** Fill logic consumes `side`, `entry_price`, `stop_price`, `take_profit_price`, `signal_ts` from intent. (FillModel: `src/axiom_bt/pipeline/fill_model.py` L65–L204)
- **Finding:** Trades are built by merging fills with intent on `template_id` and require `side` from intent. (Execution: `src/axiom_bt/pipeline/execution.py` L65–L110)
- **Compliance:** For tested runs, contract appears **compliant**: no fills/trades without a matching intent and no multi-side intents per template_id.

## 1) SSOT Contract Definition (Intent → Fill → Trade)
**Key:** `template_id` is the join key across `events_intent.csv`, `fills.csv`, `trades.csv`.

**Required fields in `events_intent.csv`** (must exist for a trade to occur):
- `template_id`, `symbol`, `side`, `signal_ts`, `entry_price`, `stop_price`, `take_profit_price`, `strategy_id`, `strategy_version`

**Allowed fields:**
- Debug/context fields derived from signal time (`sig_*`, `dbg_*`) and **scheduled validity** (`order_valid_to_ts`, `order_valid_to_reason`, `dbg_valid_*`).

**Forbidden in intent (outcomes):**
- Actual fill prices, realized pnl, trade exit prices, actual trade exit reasons.

**Rule:** If required intent fields are missing, the pipeline must not create fills/trades.

## 2) Write Path & Consumption Path (Code Proof)
### Intent generation
- **File:** `src/axiom_bt/pipeline/signals.py`
- **Function:** `generate_intent(...)` (L64–L189)
- **Evidence:** intent built from `signal_side`, `entry_price`, `stop_price`, `take_profit_price` with `template_id` and `signal_ts`. (L96–L107)
- **Evidence:** intent is sanitized (`sanitize_intent`) before write (L170–L178)

### Artifact write
- **File:** `src/axiom_bt/pipeline/artifacts.py`
- **Function:** `write_artifacts(...)` (L28–L58)
- **Evidence:** writes `events_intent.csv`, `fills.csv`, `trades.csv` directly (L43–L46)

### Fill generation
- **File:** `src/axiom_bt/pipeline/fill_model.py`
- **Function:** `generate_fills(...)` (L65–L204)
- **Evidence:** uses `events_intent` rows; requires `side`, `entry_price`, `stop_price`, `take_profit_price` (L96–L133)
- **Evidence:** entry fill uses signal_ts bar + insidebar stop/cross logic keyed by intent data (L97–L128)

### Trade construction
- **File:** `src/axiom_bt/pipeline/execution.py`
- **Function:** `_build_trades(...)` (L41–L202)
- **Evidence:** entry/exit fills grouped by `template_id` then merged with `events_intent` on `template_id` (L65–L110)
- **Evidence:** `side` is required from intent; error if missing (L91–L93)

## 3) OCO / Directionality Behavior (As Implemented)
- **InsideBar core uses a single, first-breakout rule:**
  - If `current.high > entry_long` → **BUY** signal; else if `current.low < entry_short` → **SELL** signal. (L535–L717)
  - This is an **if/elif** sequence; only one side can be produced per bar. No OCO pairing.
- **Implication:** The system **does not generate two intents** (BUY+SELL) for the same setup. It generates one intent at the breakout decision point.

## 4) Mutation / Lookahead Check
- No evidence of post-hoc enrichment of `events_intent` after `generate_intent(...)` in the pipeline path.
- `events_intent` is created in `generate_intent(...)`, sanitized via `sanitize_intent`, and then written to disk as-is.
- Validity timestamps (`order_valid_to_ts`, `dbg_valid_*`) are **scheduled at intent time** (session_end policy) and do not represent realized outcomes.

## 5) Data Evidence (2 Runs, 3 Case Studies)
See:
- `docs/audits/intent_case_studies_order_truth.md`
- `docs/audits/intent_fill_trade_join_keys.md`

Summary:
- For both runs, **fills/trades only reference template_ids present in intents**.
- **No template_id** appears with both BUY and SELL sides in intents (no OCO pairs).

## 6) Compliance Verdict
**Result: Compliant (within scope tested).**
- Fills and trades are derived from intents keyed by `template_id`.
- No evidence of trades or fills without a matching intent row.
- Directionality is single-sided per setup; no OCO present.

## 7) Next Steps (Read-only checks / Proposed tests)
- Add a regression test: fails if any fill/trade template_id not in intents.
- Add a regression test: no multi-side intents per template_id unless an explicit OCO mode is implemented.

## Repro Commands Used
- `rg -n "events_intent|intent|generate_intent|fills.csv|trades.csv|template_id" src/axiom_bt -S`
- `nl -ba src/axiom_bt/pipeline/signals.py | sed -n '1,230p'`
- `nl -ba src/axiom_bt/pipeline/fill_model.py | sed -n '1,260p'`
- `nl -ba src/axiom_bt/pipeline/execution.py | sed -n '1,260p'`
- `nl -ba src/axiom_bt/pipeline/artifacts.py | sed -n '1,120p'`
- `python` script for case studies + join checks (see generated audit files)
