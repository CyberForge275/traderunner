# Fill Semantics SSOT

This document defines deterministic fill behavior for backtests.

## Signal Time Contract (Next-Bar Semantics)
- `signal_ts` is the start timestamp of the bar **after** the InsideBar.
- Trigger scanning begins at `signal_ts` (inclusive) and ends at `order_valid_to_ts` (inclusive).
- Fills must never occur before `signal_ts`.

## Trigger Rules (Entry)
- BUY triggers if `bar.high >= entry_price`.
- SELL triggers if `bar.low <= entry_price`.

## OCO Two-Leg Semantics (v1.0.2)
- For each setup, the strategy emits **two legs** (BUY + SELL) with the same `oco_group_id`.
- At most **one entry fill** per `oco_group_id`.
- When one leg fills, the other leg is immediately cancelled and recorded in `fills.csv`.

### Reasons (audit strings)
- Entry: `signal_fill`
- OCO Cancel: `order_cancelled_oco`
- Ambiguous same-bar trigger: `order_ambiguous_no_fill`
- Netting block: `order_rejected_netting_open_position`

### Ambiguous Same-Bar Policy
If both BUY and SELL would trigger on the same bar timestamp:
- No entry fill is produced.
- Two audit rows are recorded with reason `order_ambiguous_no_fill`.

### Netting (Fill Layer Only)
- Netting is enforced in `fill_model`, not in the strategy layer.
- If a trigger occurs while a position is still open for the same symbol, emit:
  - reason `order_rejected_netting_open_position`
  - `fill_ts` at the trigger bar timestamp
  - `fill_price` NaN

### Invariants
- `events_intent.csv` is immutable after creation.
- Cancel or ambiguous rows **must not** create trades.
- Max one entry fill per `oco_group_id`.
