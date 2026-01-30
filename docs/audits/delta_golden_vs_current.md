# Delta Analysis — Golden vs Current

Golden: `260125_122357_HOOD_IB_refactor5_180d`
Current: `260130_103758_HOOD_IB_sessionWindow2_300d`

## A) Golden Snapshot
```json
{
  "strategy_id": "insidebar_intraday",
  "strategy_version": "1.0.1",
  "timeframe_minutes": 5,
  "session_timezone": "America/New_York",
  "session_filter": [
    "09:30-11:00",
    "14:00-15:00"
  ],
  "valid_from_policy": "signal_ts",
  "order_validity_policy": "session_end",
  "breakout_confirmation": true,
  "fees_bps": 2.0,
  "slippage_bps": 1.0,
  "compound_sizing": null,
  "compound_equity_basis": "cash_only",
  "requested_end": "2026-01-24",
  "lookback_days": 180,
  "counts": {
    "intents": 183,
    "fills": 176,
    "trades": 176
  },
  "coverage": {
    "intents_tid_pct": 100.0,
    "fills_tid_pct": 100.0,
    "trades_tid_pct": null
  },
  "exit_reason_trades": {
    "take_profit": 88,
    "stop_loss": 60,
    "session_end": 28
  },
  "exit_reason_fills": {
    "validity_fill": 176
  },
  "intents_exit_ts_null_pct": 0.0,
  "entry_eq_exit_pct": 0.0,
  "entry_in_session_pct": 100.0,
  "exit_at_session_end_pct": 19.318181818181817,
  "dbg_columns": [
    "dbg_signal_ts_ny",
    "dbg_signal_ts_berlin",
    "dbg_exit_ts_ny",
    "dbg_trigger_ts",
    "dbg_inside_ts",
    "dbg_mother_ts",
    "dbg_breakout_level",
    "dbg_mother_high",
    "dbg_mother_low",
    "dbg_mother_range",
    "dbg_valid_from_ts",
    "dbg_valid_from_ts_utc",
    "dbg_valid_from_ts_ny",
    "dbg_valid_to_ts",
    "dbg_valid_to_ts_utc",
    "dbg_valid_to_ts_ny",
    "dbg_order_expired",
    "dbg_order_expire_reason",
    "dbg_effective_valid_from_policy"
  ],
  "sig_columns": [],
  "range_info": {
    "events_signal_ts": [
      "2025-07-29 18:30:00+00:00",
      "2026-01-23 19:25:00+00:00"
    ],
    "fills_fill_ts": [
      "2025-07-29 18:35:00+00:00",
      "2026-01-23 19:30:00+00:00"
    ],
    "trades_entry_ts": [
      "2025-07-29 18:35:00+00:00",
      "2026-01-23 19:30:00+00:00"
    ],
    "trades_exit_ts": [
      "2025-07-29 19:00:00+00:00",
      "2026-01-23 20:00:00+00:00"
    ],
    "equity_ts": [
      "None",
      "None"
    ]
  }
}
```

## B) Current Snapshot
```json
{
  "strategy_id": "insidebar_intraday",
  "strategy_version": "1.0.1",
  "timeframe_minutes": 5,
  "session_timezone": "America/New_York",
  "session_filter": [
    "09:30-11:00",
    "14:00-15:00"
  ],
  "valid_from_policy": "signal_ts",
  "order_validity_policy": "session_end",
  "breakout_confirmation": true,
  "fees_bps": 2.0,
  "slippage_bps": 1.0,
  "compound_sizing": true,
  "compound_equity_basis": "cash_only",
  "requested_end": "2026-01-29",
  "lookback_days": 300,
  "counts": {
    "intents": 308,
    "fills": 308,
    "trades": 308
  },
  "coverage": {
    "intents_tid_pct": 100.0,
    "fills_tid_pct": 100.0,
    "trades_tid_pct": 100.0
  },
  "exit_reason_trades": {
    "session_end": 308
  },
  "exit_reason_fills": {
    "signal_fill": 308
  },
  "intents_exit_ts_null_pct": 100.0,
  "entry_eq_exit_pct": 0.0,
  "entry_in_session_pct": 100.0,
  "exit_at_session_end_pct": 100.0,
  "dbg_columns": [],
  "sig_columns": [],
  "range_info": {
    "events_signal_ts": [
      "2025-04-04 14:05:00+00:00",
      "2026-01-28 19:15:00+00:00"
    ],
    "fills_fill_ts": [
      "2025-04-04 14:05:00+00:00",
      "2026-01-28 19:15:00+00:00"
    ],
    "trades_entry_ts": [
      "2025-04-04 14:05:00+00:00",
      "2026-01-28 19:15:00+00:00"
    ],
    "trades_exit_ts": [
      "2025-04-04 19:00:00+00:00",
      "2026-01-28 20:00:00+00:00"
    ],
    "equity_ts": [
      "None",
      "None"
    ]
  }
}
```

## C) Delta Summary (Top 10)
| Metric | Golden | Current |
|---|---:|---:|
| intents | 183 | 308 |
| fills | 176 | 308 |
| trades | 176 | 308 |
| intents_exit_ts_null_pct | 0.0 | 100.0 |
| entry_eq_exit_pct | 0.0 | 0.0 |
| entry_in_session_pct | 100.0 | 100.0 |
| exit_at_session_end_pct | 19.318181818181817 | 100.0 |

## D) Column Diff — events_intent
Only in Golden: ['breakout_confirmation', 'dbg_breakout_level', 'dbg_effective_valid_from_policy', 'dbg_exit_ts_ny', 'dbg_inside_ts', 'dbg_mother_high', 'dbg_mother_low', 'dbg_mother_range', 'dbg_mother_ts', 'dbg_order_expire_reason', 'dbg_order_expired', 'dbg_signal_ts_berlin', 'dbg_signal_ts_ny', 'dbg_trigger_ts', 'dbg_valid_from_ts', 'dbg_valid_from_ts_ny', 'dbg_valid_from_ts_utc', 'dbg_valid_to_ts', 'dbg_valid_to_ts_ny', 'dbg_valid_to_ts_utc', 'risk_distance_filtered', 'valid_from_policy']

Only in Current: []

## E) Column Diff — fills
Only in Golden: ['dbg_fill_ts_ny']

Only in Current: []

## F) Column Diff — trades
Only in Golden: ['dbg_entry_ts_ny', 'dbg_exit_ts_ny']

Only in Current: ['template_id']


## G) Evidence Greps (captured output)
```text
rg -n "dbg_" artifacts/backtests/260125_122357_HOOD_IB_refactor5_180d/events_intent.csv | head
1:template_id,signal_ts,dbg_signal_ts_ny,dbg_signal_ts_berlin,symbol,side,entry_price,stop_price,take_profit_price,exit_ts,dbg_exit_ts_ny,exit_reason,strategy_id,strategy_version,breakout_confirmation,valid_from_policy,risk_distance_filtered,dbg_trigger_ts,dbg_inside_ts,dbg_mother_ts,dbg_breakout_level,dbg_mother_high,dbg_mother_low,dbg_mother_range,dbg_valid_from_ts,dbg_valid_from_ts_utc,dbg_valid_from_ts_ny,dbg_valid_to_ts,dbg_valid_to_ts_utc,dbg_valid_to_ts_ny,dbg_order_expired,dbg_order_expire_reason,dbg_effective_valid_from_policy

rg -n "sig_" artifacts/backtests/260130_103758_HOOD_IB_sessionWindow2_300d/events_intent.csv | head
<no matches>

rg -n "stop_loss|take_profit|session_end|signal_fill" artifacts/backtests/260130_103758_HOOD_IB_sessionWindow2_300d/fills.csv artifacts/backtests/260130_103758_HOOD_IB_sessionWindow2_300d/trades.csv | head
artifacts/backtests/260130_103758_HOOD_IB_sessionWindow2_300d/fills.csv:2:ib_HOOD_20250404_140500,HOOD,2025-04-04 14:05:00+00:00,33.45,signal_fill
artifacts/backtests/260130_103758_HOOD_IB_sessionWindow2_300d/fills.csv:3:ib_HOOD_20250404_183500,HOOD,2025-04-04 18:35:00+00:00,34.05,signal_fill
artifacts/backtests/260130_103758_HOOD_IB_sessionWindow2_300d/fills.csv:4:ib_HOOD_20250407_143500,HOOD,2025-04-07 14:35:00+00:00,32.96,signal_fill
artifacts/backtests/260130_103758_HOOD_IB_sessionWindow2_300d/fills.csv:5:ib_HOOD_20250408_140000,HOOD,2025-04-08 14:00:00+00:00,37.5298,signal_fill
artifacts/backtests/260130_103758_HOOD_IB_sessionWindow2_300d/fills.csv:6:ib_HOOD_20250408_181500,HOOD,2025-04-08 18:15:00+00:00,35.38,signal_fill
```
