# Delta Golden vs Parity — 2026-01-22 (NY)


Golden: `artifacts/backtests/260125_122357_HOOD_IB_refactor5_180d`

Parity: `artifacts/backtests/260130_153000_HOOD_IB_parity_dbgfill`

Symbol: `HOOD`

Day (NY): `2026-01-22`


## Column Inventory

Golden dbg_*: ['dbg_breakout_level', 'dbg_effective_valid_from_policy', 'dbg_exit_ts_ny', 'dbg_inside_ts', 'dbg_mother_high', 'dbg_mother_low', 'dbg_mother_range', 'dbg_mother_ts', 'dbg_order_expire_reason', 'dbg_order_expired', 'dbg_signal_ts_berlin', 'dbg_signal_ts_ny', 'dbg_trigger_ts', 'dbg_valid_from_ts', 'dbg_valid_from_ts_ny', 'dbg_valid_from_ts_utc', 'dbg_valid_to_ts', 'dbg_valid_to_ts_ny', 'dbg_valid_to_ts_utc']


Parity dbg_*: ['dbg_breakout_level', 'dbg_effective_valid_from_policy', 'dbg_exit_ts_ny', 'dbg_inside_ts', 'dbg_mother_high', 'dbg_mother_low', 'dbg_mother_range', 'dbg_mother_ts', 'dbg_order_expire_reason', 'dbg_order_expired', 'dbg_signal_ts_berlin', 'dbg_signal_ts_ny', 'dbg_trigger_ts', 'dbg_valid_from_ts', 'dbg_valid_from_ts_ny', 'dbg_valid_from_ts_utc', 'dbg_valid_to_ts', 'dbg_valid_to_ts_ny', 'dbg_valid_to_ts_utc']


Golden sig_*: []


Parity sig_*: ['sig_atr', 'sig_entry_price', 'sig_inside_bar', 'sig_inside_ts', 'sig_mother_high', 'sig_mother_low', 'sig_mother_ts', 'sig_stop_price', 'sig_take_profit_price']


## Counts

Golden intents (day): 2

Parity intents (day): 2


## Matching Summary

Match key: ['symbol', 'side', 'dbg_trigger_ts']

Common: 2

Only Golden: 0

Only Parity: 0


## COMMON Diffs (Entry/SL/TP)

CSV: `docs/audits/delta_golden_vs_parity_2026-01-22_dbgfill_common.csv`


## Fills/Trades Cross-Check (COMMON)

Columns include fills_count_*, fills_reasons_*, trade_present_*, trade_exit_reason_*.


## Only in Golden

(none)



## Only in Parity

(none)


