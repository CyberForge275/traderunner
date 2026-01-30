# DBG Parity Readiness — Golden vs Parity


Golden dbg_*: ['dbg_breakout_level', 'dbg_effective_valid_from_policy', 'dbg_exit_ts_ny', 'dbg_inside_ts', 'dbg_mother_high', 'dbg_mother_low', 'dbg_mother_range', 'dbg_mother_ts', 'dbg_order_expire_reason', 'dbg_order_expired', 'dbg_signal_ts_berlin', 'dbg_signal_ts_ny', 'dbg_trigger_ts', 'dbg_valid_from_ts', 'dbg_valid_from_ts_ny', 'dbg_valid_from_ts_utc', 'dbg_valid_to_ts', 'dbg_valid_to_ts_ny', 'dbg_valid_to_ts_utc']


Parity dbg_*: ['dbg_breakout_level', 'dbg_effective_valid_from_policy', 'dbg_exit_ts_ny', 'dbg_inside_ts', 'dbg_mother_high', 'dbg_mother_low', 'dbg_mother_range', 'dbg_mother_ts', 'dbg_order_expire_reason', 'dbg_order_expired', 'dbg_signal_ts_berlin', 'dbg_signal_ts_ny', 'dbg_trigger_ts', 'dbg_valid_from_ts', 'dbg_valid_from_ts_ny', 'dbg_valid_from_ts_utc', 'dbg_valid_to_ts', 'dbg_valid_to_ts_ny', 'dbg_valid_to_ts_utc']


Golden sig_*: []


Parity sig_*: ['sig_atr', 'sig_entry_price', 'sig_inside_bar', 'sig_inside_ts', 'sig_mother_high', 'sig_mother_low', 'sig_mother_ts', 'sig_stop_price', 'sig_take_profit_price']


## Required dbg_* missing in Parity

()


## Coverage (non-null %)

| column                          | golden_exists   | parity_exists   |   golden_non_null_pct |   parity_non_null_pct |
|:--------------------------------|:----------------|:----------------|----------------------:|----------------------:|
| dbg_breakout_level              | True            | True            |             100       |                   100 |
| dbg_effective_valid_from_policy | True            | True            |             100       |                   100 |
| dbg_exit_ts_ny                  | True            | True            |             100       |                   100 |
| dbg_inside_ts                   | True            | True            |             100       |                   100 |
| dbg_mother_high                 | True            | True            |             100       |                   100 |
| dbg_mother_low                  | True            | True            |             100       |                   100 |
| dbg_mother_range                | True            | True            |             100       |                   100 |
| dbg_mother_ts                   | True            | True            |             100       |                   100 |
| dbg_order_expire_reason         | True            | True            |               3.82514 |                     0 |
| dbg_order_expired               | True            | True            |             100       |                   100 |
| dbg_signal_ts_berlin            | True            | True            |             100       |                   100 |
| dbg_signal_ts_ny                | True            | True            |             100       |                   100 |
| dbg_trigger_ts                  | True            | True            |             100       |                   100 |
| dbg_valid_from_ts               | True            | True            |              96.1749  |                   100 |
| dbg_valid_from_ts_ny            | True            | True            |              96.1749  |                   100 |
| dbg_valid_from_ts_utc           | True            | True            |              96.1749  |                   100 |
| dbg_valid_to_ts                 | True            | True            |              96.1749  |                   100 |
| dbg_valid_to_ts_ny              | True            | True            |              96.1749  |                   100 |
| dbg_valid_to_ts_utc             | True            | True            |              96.1749  |                   100 |