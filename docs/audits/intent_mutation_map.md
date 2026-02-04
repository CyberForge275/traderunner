# Intent mutation map (post-generation)

## Summary
- `events_intent` is generated once in `generate_intent(...)` and passed read-only through fill and execution stages.
- No in-place mutation of `events_intent` is performed before writing artifacts.

## Evidence
- `src/axiom_bt/pipeline/runner.py:190-224` — `intent_art.events_intent` passed to `generate_fills(...)` and `execute(...)`.
- `src/axiom_bt/pipeline/fill_model.py:35-153` — iterates `events_intent.iterrows()`; no writes to `events_intent`.
- `src/axiom_bt/pipeline/execution.py:90-107` — creates `intent_df = events_intent.copy()` and mutates the copy only.
- `src/axiom_bt/pipeline/artifacts.py:28-45` — writes `events_intent` directly to `events_intent.csv`.

## Noted copy/mutation points (non-persistent)
- `execution._build_trades(...)` adds `exit_ts` / `exit_reason` defaults **on a copy** (`intent_df`) and merges with fills; does not persist back to `events_intent`.

## Implication
Any lookahead fields in `events_intent.csv` originate from `generate_intent(...)` (or upstream `signals_frame`), not from post-hoc enrichment in execution/fill layers.
