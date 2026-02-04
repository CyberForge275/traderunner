# Trade Inspector Chart Windowing

## Window Rule
- Start: **mother_ts - 5 bars** (by index, not by minutes)
- End: **exit_ts + 5 bars** (fallback: dbg_valid_to_ts_utc; if missing, end at mother_ts + 5 bars)

## Timestamp Resolution (priority)
- mother_ts: `dbg_mother_ts` → `sig_mother_ts` → `mother_ts`
- inside_ts: `dbg_inside_ts` → `sig_inside_ts` → `inside_ts`
- exit_ts: `exit_ts` → `dbg_valid_to_ts_utc` → `dbg_exit_ts_utc` → `dbg_valid_to_ts`

All timestamps are normalized to UTC (`pd.to_datetime(..., utc=True)`), then aligned to the nearest **previous** bar in the window.

## Marker Rules
- Motherbar: blue triangle-down above bar high (`high * 1.002`)
- InsideBar: black triangle-down above bar high (`high * 1.002`)
- Entry: green triangle-up below bar low (`low * 0.998`)

## Logging (examples)
- `actions: inspector_open table=orders template_id=... symbol=... ts=...`
- `actions: inspector_chart_window kind=orders ... bars=<n>`

## Fallbacks
- If bars are missing or timestamp alignment fails, chart displays **No bars available** and logs the reason.
