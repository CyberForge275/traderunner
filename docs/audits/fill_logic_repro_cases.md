# Fill Logic Repro Cases

Run: `260203_002422_HOOD_IB_pipeline1_300d`

## Case 1: HOOD BUY target 2025-09-08 13:45:00+00:00

template_id: `ib_HOOD_20250908_134500`

signal_ts: `2025-09-08 13:45:00+00:00`


**Intent**

- entry_price: 113.52
- stop_price: 113.12
- take_profit_price: 114.32


**Entry Fill**

- fill_ts: 2025-09-08 13:45:00+00:00
- fill_price: 113.531352


**Exit Fill**

- reason: take_profit
- fill_ts: 2025-09-08 13:50:00+00:00
- fill_price: 114.32


**Trade**

- entry_price: 113.531352
- exit_price: 114.32
- reason: take_profit
- pnl: 62.3031919999996


**Invariant OK**: True


## Case 2: HOOD BUY target 2025-11-04 14:40:00+00:00

template_id: `ib_HOOD_20251104_144000`

signal_ts: `2025-11-04 14:40:00+00:00`


**Intent**

- entry_price: 140.74
- stop_price: 140.34
- take_profit_price: 141.54000000000002


**Entry Fill**

- fill_ts: 2025-11-04 14:40:00+00:00
- fill_price: 140.754074


**Exit Fill**

- reason: take_profit
- fill_ts: 2025-11-04 14:45:00+00:00
- fill_price: 141.54000000000002


**Trade**

- entry_price: 140.754074
- exit_price: 141.54000000000002
- reason: take_profit
- pnl: 51.08519000000115


**Invariant OK**: True


## Case 3: HOOD SELL target 2025-10-17 14:10:00+00:00

template_id: `ib_HOOD_20251017_141000`

signal_ts: `2025-10-17 14:10:00+00:00`


**Intent**

- entry_price: 129.0408
- stop_price: 129.4408
- take_profit_price: 128.24079999999998


**Entry Fill**

- fill_ts: 2025-10-17 14:10:00+00:00
- fill_price: 129.02789592


**Exit Fill**

- reason: stop_loss
- fill_ts: 2025-10-17 14:15:00+00:00
- fill_price: 129.4408


**Trade**

- entry_price: 129.02789592
- exit_price: 129.4408
- reason: stop_loss
- pnl: -29.31618968000029


**Invariant OK**: True

