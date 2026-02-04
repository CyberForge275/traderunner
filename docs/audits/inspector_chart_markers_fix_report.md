# Inspector Chart Markers Fix Report

## Scope
- UI only (Inspector modal + chart markers)
- No changes to candles, backtest pipeline, or strategy logic

## Files changed
- `trading_dashboard/assets/trade_inspector.css`
- `trading_dashboard/components/row_inspector.py`
- `trading_dashboard/components/signal_chart.py`
- `trading_dashboard/callbacks/backtests_callbacks.py`
- `tests/test_signal_chart.py`

## What changed (high level)
1) **Modal width override**
   - Added modal class and CSS override to defeat hard caps in `trade_inspector.css`.
   - Ensures right chart panel is visibly wider.

2) **Marker windowing and alignment**
   - Window uses **union** of mother/inside/entry/exit timestamps to avoid missing markers.
   - Deterministic alignment to nearest previous bar in UTC.
   - Marker placement uses OHLC from aligned bar with deterministic offset.
   - Logs for skip reasons and alignment details.

3) **Tests**
   - Added unit tests for marker alignment, union windowing, and out-of-window handling.

## Modal width override (CSS)
- `trade_inspector.css` adds `.trade-inspector-modal .modal-dialog` rules:
  - `width: min(95vw, 1800px)`
  - `max-width: min(95vw, 1800px)`
  - `--bs-modal-width: min(95vw, 1800px)`

## Marker logic (code)
### Windowing (union)
- `compute_bars_window_union` takes relevant timestamps:
  - mother_ts, inside_ts, entry_ts, exit_ts (non-null)
- window_start = min(relevant_ts) - 5 bars
- window_end = max(relevant_ts) + 5 bars

### Marker placement
- Mother: triangle-down blue, high + offset
- Inside: triangle-down black, high + offset
- Entry: triangle-up green, low - offset
- Offset = 2% of (window_high - window_low), fallback 0

### Logging (actions: prefix)
Examples:
- `actions: inspector_marker key=mother wanted_ts=... aligned_ts=... y=... window_min=... window_max=...`
- `actions: inspector_marker key=inside reason=out_of_window ...`
- `actions: inspector_marker key=entry reason=no_price ...`

## Tests executed
```
PYTHONPATH=src:. pytest -q tests/test_signal_chart.py -q
```

## Expected behavior
- Modal is visibly wider (chart panel ~2.25x of left column)
- Markers render for mother/inside/entry when timestamps are in dataset
- Missing markers emit explicit log reason

