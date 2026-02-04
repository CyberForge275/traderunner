# Intent Purity Audit v1 (read-only)

## Definition (SSOT for this audit)
- **intent_generated_ts = end of inside bar (M5 close)**.
- Evidence for inside-bar timing in strategy wiring:
  - `src/strategies/inside_bar/__init__.py:176-183` uses `inside_ts` from the inside bar index (`df.at[ib_idx, "timestamp"]`).
  - `src/axiom_bt/pipeline/signals.py:95-105` sets `signal_ts = sig["timestamp"]` (the signal bar timestamp).

## Schema (current events_intent.csv)
From runs:
- `260202_090827__HOOD_IB_maxLossPCT001_300d`
- `260202_090625_HOOD_IB_maxLossPct0_300d`
- `260203_221225_HOOD_IB_allign2golden_300d`

All three runs share the same 40 columns:
```
['template_id','signal_ts','symbol','side','entry_price','stop_price','take_profit_price','exit_ts','exit_reason',
 'strategy_id','strategy_version','breakout_confirmation','dbg_signal_ts_ny','dbg_signal_ts_berlin',
 'dbg_effective_valid_from_policy','dbg_valid_to_ts_utc','dbg_valid_to_ts_ny','dbg_valid_to_ts','dbg_exit_ts_ny',
 'dbg_valid_from_ts_utc','dbg_valid_from_ts','dbg_valid_from_ts_ny','sig_atr','sig_inside_bar','sig_mother_high',
 'sig_mother_low','sig_entry_price','sig_stop_price','sig_take_profit_price','sig_mother_ts','sig_inside_ts',
 'dbg_breakout_level','dbg_mother_high','dbg_mother_low','dbg_mother_ts','dbg_inside_ts','dbg_trigger_ts',
 'dbg_order_expired','dbg_order_expire_reason','dbg_mother_range']
```

### Classification
✅ **allowed_at_intent_time** (signals + params at inside-bar close)
- template_id, signal_ts, symbol, side, entry_price, stop_price, take_profit_price
- strategy_id, strategy_version, breakout_confirmation
- sig_* fields (copied from signal_frame)
- dbg_mother_*, dbg_inside_ts, dbg_breakout_level, dbg_mother_range
- dbg_valid_from_ts_* (derived from policy and signal_ts)
- dbg_signal_ts_* (timezone view of signal_ts)

⚠️ **scheduled_validity** (policy-known, but future-dated)
- exit_ts, exit_reason (set when order_validity_policy=session_end)
- dbg_valid_to_ts_utc, dbg_valid_to_ts_ny, dbg_valid_to_ts, dbg_exit_ts_ny

❌ **forbidden_future_outcome** (should not exist at intent time)
- none observed in events_intent (no fill_price/pnl/etc.)

## Write-path proof (intent creation + write)
- `src/axiom_bt/pipeline/signals.py:63-177` → builds `events_intent`.
  - `exit_ts`/`exit_reason` and `dbg_valid_to_*` set when `order_validity_policy == "session_end"` (`signals.py:118-129`).
  - `dbg_trigger_ts` set from `sig.trigger_ts` or falls back to `signal_ts` (`signals.py:161-164`).
- `src/axiom_bt/pipeline/runner.py:190-224` → passes `events_intent` to fills/execution.
- `src/axiom_bt/pipeline/artifacts.py:28-45` → writes `events_intent.csv`.

## Evidence rows (future-dated fields present)
Run: `260202_090827__HOOD_IB_maxLossPCT001_300d`

Example rows:
```
ib_HOOD_20250407_185500: signal_ts=2025-04-07 18:55:00+00:00, dbg_trigger_ts=2025-04-07 18:55:00+00:00,
  exit_ts=2025-04-07 19:00:00+00:00, dbg_valid_to_ts_utc=2025-04-07 19:00:00+00:00, dbg_exit_ts_ny=2025-04-07 15:00:00-04:00
ib_HOOD_20250408_134000: signal_ts=2025-04-08 13:40:00+00:00, dbg_trigger_ts=2025-04-08 13:40:00+00:00,
  exit_ts=2025-04-08 15:00:00+00:00, dbg_valid_to_ts_utc=2025-04-08 15:00:00+00:00, dbg_exit_ts_ny=2025-04-08 11:00:00-04:00
ib_HOOD_20250408_181500: signal_ts=2025-04-08 18:15:00+00:00, dbg_trigger_ts=2025-04-08 18:15:00+00:00,
  exit_ts=2025-04-08 19:00:00+00:00, dbg_valid_to_ts_utc=2025-04-08 19:00:00+00:00, dbg_exit_ts_ny=2025-04-08 15:00:00-04:00
```
These values are **scheduled** at intent time, but they are **future-dated** relative to signal time.

## Conclusion (read-only)
- No direct fill/trade outcomes leak into `events_intent.csv`.
- **However:** `exit_ts` and `dbg_valid_to_*` are future-dated fields embedded at intent time. If the SSOT requires zero future information, these must be removed or renamed as validity-only fields (and strictly treated as policy schedule, not realized exits).
