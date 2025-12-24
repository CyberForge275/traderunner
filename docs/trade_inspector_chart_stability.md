# Trade Inspector Chart Stability

## Root Cause (observed)
Plotly/Dash was entering a resize/relayout loop when rendering the Trade Inspector chart, causing the container height to grow indefinitely. Likely triggers: responsive/autosize plus hidden/rehydrated container with ResizeObserver relayouts.

## Fix (forward)
- Fixed-size container with scoped CSS (`ti-chart-shell`, `ti-chart-graph`).
- Figure layout hardened: fixed width/height, `uirevision="constant"`, no transitions, hovermode `closest`, fixed ranges.
- Removed autoscale/zoom/pan/lasso buttons from modebar.
- One-shot clientside resize per trade selection using `ti-resize-request`/`ti-resize-ack` stores; no intervals/polling.
- Lazy-ish render: graph updates only on run/trade selection.

## How to verify manually
1. Hard refresh the dashboard.
2. Open the "🔍 Trade Inspector" tab.
3. Select a run and a trade.
4. Observe the chart area for 30 seconds; height should stay ~600px (no growth).

## Tests
- Unit: `tests/dashboard/test_trade_inspector_plot.py` checks stable layout (height/width/uirevision).
- Optional local Playwright smoke (not in CI): load page, select run/trade, poll graph container height < 800px over 10s.
