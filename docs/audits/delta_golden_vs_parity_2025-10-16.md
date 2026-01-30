# Delta Golden vs Parity — 2026-01-22 (NY)


Golden: `artifacts/backtests/260125_122357_HOOD_IB_refactor5_180d`

Parity: `artifacts/backtests/260130_120607_HOOD_IB_goldenParity_300d`

Symbol: `HOOD`

Day (NY): `2025-10-16`


## Column Inventory

Golden dbg_*: ['dbg_breakout_level', 'dbg_effective_valid_from_policy', 'dbg_exit_ts_ny', 'dbg_inside_ts', 'dbg_mother_high', 'dbg_mother_low', 'dbg_mother_range', 'dbg_mother_ts', 'dbg_order_expire_reason', 'dbg_order_expired', 'dbg_signal_ts_berlin', 'dbg_signal_ts_ny', 'dbg_trigger_ts', 'dbg_valid_from_ts', 'dbg_valid_from_ts_ny', 'dbg_valid_from_ts_utc', 'dbg_valid_to_ts', 'dbg_valid_to_ts_ny', 'dbg_valid_to_ts_utc']


Parity dbg_*: ['dbg_effective_valid_from_policy', 'dbg_valid_from_ts', 'dbg_valid_from_ts_ny', 'dbg_valid_from_ts_utc', 'dbg_valid_to_ts', 'dbg_valid_to_ts_ny', 'dbg_valid_to_ts_utc']


Golden sig_*: []


Parity sig_*: ['sig_atr', 'sig_entry_price', 'sig_inside_bar', 'sig_mother_high', 'sig_mother_low', 'sig_stop_price', 'sig_take_profit_price']


## Counts

Golden intents (day): 2

Parity intents (day): 2


## Matching Summary

Match key: ['symbol', 'side', 'signal_ts']

Common: 2

Only Golden: 0

Only Parity: 0


## COMMON Diffs (Entry/SL/TP)

CSV: `docs/audits/delta_golden_vs_parity_2025-10-16_common.csv`


## Fills/Trades Cross-Check (COMMON)

Columns include fills_count_*, fills_reasons_*, trade_present_*, trade_exit_reason_*.


### Top 10 DIFF rows

| signal_ts                 | template_id_g   | template_id_p           | side   |   entry_price_g |   entry_price_p |   delta_entry_price | diff_entry_price   |   stop_price_g |   stop_price_p |   delta_stop_price | diff_stop_price   |   take_profit_price_g |   take_profit_price_p |   delta_take_profit_price | diff_take_profit_price   |
|:--------------------------|:----------------|:------------------------|:-------|----------------:|----------------:|--------------------:|:-------------------|---------------:|---------------:|-------------------:|:------------------|----------------------:|----------------------:|--------------------------:|:-------------------------|
| 2025-10-16 14:50:00+00:00 | ib_tpl_13432    | ib_HOOD_20251016_145000 | BUY    |           136.4 |          136.16 |             -0.2399 | True               |            136 |         135.76 |            -0.2399 | True              |                 137.2 |                136.96 |                   -0.2399 | True                     |



## Only in Golden

(none)



## Only in Parity

(none)



## DBG Evidence (Top 10 DIFF rows)

| signal_ts                 | dbg_valid_from_ts_utc_g   | dbg_valid_from_ts_utc_p   | dbg_valid_to_ts_utc_g     | dbg_valid_to_ts_utc_p     | dbg_effective_valid_from_policy_g   | dbg_effective_valid_from_policy_p   |
|:--------------------------|:--------------------------|:--------------------------|:--------------------------|:--------------------------|:------------------------------------|:------------------------------------|
| 2025-10-16 14:50:00+00:00 | 2025-10-16 14:55:00+00:00 | 2025-10-16 14:50:00+00:00 | 2025-10-16 15:00:00+00:00 | 2025-10-16 19:00:00+00:00 | next_bar                            | signal_ts                           |


