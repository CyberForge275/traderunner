# Intent Contract (SSOT)

## Definition
**Intent** is an order snapshot generated at **inside bar close (M5)**.  
It must contain only information known at intent time. No trigger/fill/trade/exit outcomes.

## Allowed vs Forbidden

### Allowed (examples)
**Core order fields**
- template_id, signal_ts, symbol, side
- entry_price, stop_price, take_profit_price
- strategy_id, strategy_version, breakout_confirmation

**Scheduled validity (policy-known)**
- order_valid_to_ts
- order_valid_to_reason
- dbg_valid_to_ts_utc / dbg_valid_to_ts_ny / dbg_valid_to_ts

**Signal-time debug (known at intent time)**
- dbg_mother_ts, dbg_inside_ts, dbg_mother_high/low/range
- dbg_breakout_level
- dbg_valid_from_ts_* and dbg_signal_ts_* (timezone views)
- sig_* columns copied from signal_frame

### Forbidden (examples)
- exit_ts, exit_reason (trade exit outcomes)
- dbg_exit_ts_* (exit outcomes)
- dbg_trigger_ts (trigger happens after intent time)
- any `fill_*`, `pnl*`, `trade_*`, `realized_*`

## Contract Enforcement
Implemented in `src/axiom_bt/artifacts/intent_contract.py`:
- drops forbidden columns
- allows only explicit allowlist + allowed prefixes
- logs violations (`actions: intent_contract_violation`)

## Rationale
This keeps `events_intent.csv` a pure order snapshot and prevents lookahead leakage.
