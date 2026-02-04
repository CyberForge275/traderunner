# Inspector Chart Markers Failure Report

## Executive Summary
- Chart is visible, but markers (Mother/Inside/Entry) do not appear consistently; modal width change does not look +50% in practice.
- Marker logic exists in callbacks, but markers are skipped when alignment yields None (missing/unaligned timestamps or window bounds).
- Modal width is likely overridden by Bootstrap modal CSS or other assets (`trade_inspector.css`) that cap width.

---

## 1) Baseline Snapshot

**pwd**
```
/home/mirko/data/workspace/droid/traderunner
```

**repo root**
```
/home/mirko/data/workspace/droid/traderunner
```

**git status -sb**
```
## main...origin/main
?? docs/audits/inspector_chart_markers_failure_report.md
?? docs/audits/moved_chart.png
```

**git log --oneline --decorate -20**
```
b43a53b (HEAD -> main, origin/main, origin/HEAD) fix(ui): stabilize inspector chart layout and markers
5cfcb7d docs(audits): add insidebar/inspector forensics artifacts
bc57c2b feat(ui): widen inspector chart + add mother/inside/entry markers
750441a feat(ui): show inspector candlestick window in order/trade inspector
251baf0 docs(audits): add git push connectivity diagnosis
5ad0e2d fix(ui): improve inspector layout and empty chart message
2911a5a fix(ui): guard missing bars timestamp in inspector chart
1c6d883 fix(ui): guard buy/sell ny columns when entry/exit missing
f643f51 feat(ui): add inspector chart window for orders and trades
e99440f chore(ssot): update insidebar_intraday.yaml params
fec468c feat(ui): add buy/sell NY timestamps to orders table
f8db063 feat(ui): add buy/sell NY timestamps to trades table
39ba354 feat(ui): add inspector modals for orders and trades
bce0f34 feat(ui): add row inspector helpers
```

**git diff --stat**
```
(no working tree diffs)
```

---

## 2) Change Timeline / Versuch 1..3

### Versuch 1 — `750441a` (Chart Window)
**Files:**
- `trading_dashboard/components/signal_chart.py`
- `trading_dashboard/callbacks/backtests_callbacks.py`

**Goal:** Render candlestick chart inside inspector.

**Key code blocks:**
- `signal_chart.compute_bars_window` (window slicing)
- `signal_chart.build_candlestick_figure` (chart rendering)
- `backtests_callbacks.open_orders_inspector/open_trades_inspector` (figure creation)

**Input keys:**
- mother_ts: `dbg_mother_ts` / fallback to `signal_ts`
- exit_ts: `exit_ts` / `dbg_valid_to_ts_utc`

**Outcome:** Chart visible; markers not yet implemented.

---

### Versuch 2 — `bc57c2b` (Layout + Markers)
**Files:**
- `row_inspector.py` (grid layout + modal width)
- `backtests_callbacks.py` (marker creation)
- `signal_chart.py` (marker helpers)
- `tests/test_signal_chart.py`

**Layout change:**
- `gridTemplateColumns: "1fr 1.5fr"`
- modal width `92vw`, `maxWidth 1600`

**Marker creation:**
- Markers added as Scatter traces in `build_candlestick_figure`.
- Marker timestamps aligned via `align_marker_ts` and prices via `resolve_marker_price`.

**Outcome:** Chart visible, but markers not visible in UI; width increase not perceived as +50%.

---

### Versuch 3 — `b43a53b` (Stabilization)
**Files:**
- `backtests_callbacks.py` (logging for marker align/missing)
- `signal_chart.py` (guard on out-of-bounds index)
- `row_inspector.py` (modal width override via `--bs-modal-width`)

**Outcome:** 500 errors resolved. Markers still not visible. Width still not +50% in actual UI.

---

## 3) Repro Setup
- Run: `260203_221225_HOOD_IB_allign2golden_300d`
- Table: Orders
- Example: `ib_HOOD_20250411_143000`
- Action: Click 🔍 in Orders table
- Observed: Candlestick visible; no markers; modal width not materially larger.

---

## 4) Data/TS Alignment Analysis

**Row keys used**
- Mother: `dbg_mother_ts`
- Inside: `dbg_inside_ts`
- Entry: `dbg_trigger_ts` (orders) / `entry_ts` (trades)

**Parsing**
- `pd.to_datetime(..., utc=True, errors="coerce")`

**Windowing**
- `compute_bars_window`: nearest previous bar, start = mother_ts - 5 bars, end = exit_ts + 5 bars

**Problem trigger**
- If `mother_ts` / `inside_ts` are outside the bars window or outside the bars dataset, `resolve_marker_price` returns `None` → marker is skipped.

---

## 5) Marker Rendering Analysis (Plotly)

**Trace type**
- `go.Scatter` with `mode="markers+text"`

**Markers skipped if**
- `marker_ts` is None (timestamp parse failed)
- `marker_price` is None (alignment failed)

**Evidence**
- Marker missing logs are present in code but not shown in provided logs (not captured in report).

---

## 6) Modal Width Analysis (Bootstrap)

**Evidence**
- `trade_inspector.css` caps modal width at 900/920px:
  - `trading_dashboard/assets/trade_inspector.css:4-17`
- Even with inline `style`, CSS with `!important` may override.

**Result**
- Layout grid ratio changes, but the outer modal width remains capped by CSS.

---

## 7) Ranked Root-Cause Hypotheses

1) **Marker skipped due to alignment → `resolve_marker_price` returns None.**
   - Evidence: alignment is nearest-previous; if ts not inside window/data, marker is skipped.

2) **Modal width capped by `trade_inspector.css`.**
   - Evidence: CSS hard-limits modal width to ~900px.

3) **Marker y-values computed but not visible due to missing low/high or NaN.**
   - Evidence: bars loader requires open/high/low/close but may still be NaN for certain rows.

---

## 8) Deterministic Next Steps (No Code)

1) Inspect computed CSS on `.modal-dialog` to confirm override from `trade_inspector.css`.
2) Add logs for marker alignment per row (wanted_ts, aligned_ts, price, window start/end).
3) Validate bars window range vs marker timestamps (explicitly log min/max bars ts).
4) Add a unit test to force marker alignment with non-exact timestamps.
5) Confirm inside_ts and trigger_ts keys exist for the row being clicked.

---

## 9) Appendix — Evidence Snippets

**Marker creation in callbacks**
```
backtests_callbacks.py:
- resolve_marker_price(...)
- align_marker_ts(...)
- markers.append({"ts": ..., "price": ..., "label": "M/IB/Entry"})
```

**Modal width settings in `row_inspector.py`**
```
style={"width": "95vw", "maxWidth": "1800px", "--bs-modal-width": "1800px"}
```

**CSS width caps**
```
trading_dashboard/assets/trade_inspector.css
  width: 900px !important
```

---

## 10) Tests
```
PYTHONPATH=src:. pytest -q tests/test_signal_chart.py -q
5 passed
```

---

End of report.
