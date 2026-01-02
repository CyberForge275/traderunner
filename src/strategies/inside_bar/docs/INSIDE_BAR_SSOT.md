# InsideBar SSOT Strategy (M5) – Spec & Implementation Notes

## Zweck
Diese Dokumentation beschreibt die **InsideBar-Strategie als SSOT** in `src/strategies/inside_bar/`.
Sie gilt für **Backtest (Replay Engine)** und **Live-Ausführung**.

## Invarianten (Fix)
- Timeframe: **M5**
- Timezone: **Europe/Berlin**
- Sessions: **Parameterized via `session_windows`** (e.g., `["15:00-16:00", "16:00-17:00"]` in Berlin Local Time)
  - **Production default**: 15:00–17:00 Berlin (2 windows as shown)
  - **Plausibility requirement**: Session windows MUST lie within RTH if backtesting with RTH data
  - **DST handling**: Times are always local to `market_tz` (Europe/Berlin), DST-safe
- Semantik: **Nur die erste Inside Bar pro Session wird gehandelt** (Session State Machine).
- Entry Default: **mother_bar**
- Trailing: implementiert, **Default OFF**, Apply-Mode: **next_bar**
- Order Validity Policy: **Parameterized via `order_validity_policy`**
  - **Options**: `session_end`, `one_bar`, `fixed_minutes`
  - **Recommended for this strategy**: `session_end` (ensures positive order duration for Replay fills)
  - **Status**: Parameter implemented; UI configuration TODO
- Max Trades per Session: **1** (Hard Limit)

## DST (Sommer-/Winterzeit)
DST = Daylight Saving Time. `Europe/Berlin` wechselt automatisch CET/CEST.
Die Session-Zeitfenster werden immer in **lokaler Berlin-Zeit** ausgewertet.
`tz_convert("Europe/Berlin")` ist DST-safe.

## Signallogik (Core)
### Session Gate
Eine Bar ist nur handelbar, wenn `timestamp` (timezone-aware) in einer der Sessions liegt.
Zusätzlich gilt für InsideBar-Detection:
- Mother Bar (prev candle) muss in derselben Session liegen wie die Inside Bar.
- Damit ist ausgeschlossen, dass eine IB direkt am Sessionstart gehandelt wird, deren Mother-Bar außerhalb liegt.

### First-IB-per-Session State Machine
Pro Session (date + session_idx) existiert ein State:
- `armed`: erste IB der Session gefunden und „gelockt“
- `done`: Session wurde bereits gehandelt
- `levels`: mother_high/low, ib_high/low, atr

Ablauf:
1) Solange nicht armed:
   - prüfe je Bar, ob sie die erste IB dieser Session ist.
   - Wenn ja: Session wird armed (spätere IBs werden ignoriert).
2) Wenn armed:
   - beobachte nur noch den Breakout der gelockten IB.
   - bei Breakout wird genau ein Signal erzeugt und die Session ist done.

### InsideBar Definition (inclusive)
- `IB.high <= Mother.high` und `IB.low >= Mother.low`

### Mother-Bar Qualitätsfilter
- `mother_range >= min_mother_bar_size * ATR`

### Entry-Level
- `entry_level_mode = mother_bar` (default):
  - LONG entry = mother_high
  - SHORT entry = mother_low
- optional: `inside_bar`:
  - LONG entry = ib_high
  - SHORT entry = ib_low

### Breakout-Kriterium
- LONG: `close > entry_long`
- SHORT: `close < entry_short`

## Risk / SL Cap / TP
- SL liegt initial auf gegenüberliegender Seite der Mother Bar:
  - LONG: SL = mother_low
  - SHORT: SL = mother_high
- SL Cap:
  - maximale Stop-Distanz = `stop_distance_cap_ticks * tick_size`
  - falls initial risk > cap → SL wird Richtung Entry verschoben
- TP:
  - `TP = entry ± (effective_risk * risk_reward_ratio)`

## Order Validity (Replay-kritisch)
Replay kann Orders nur füllen, wenn sie **eine positive Zeitdauer** aktiv sind.
Default: `order_validity_policy = session_end`.

Wichtig:
- Bei `valid_from_policy = next_bar` wird `session_end` aus **valid_from** berechnet,
  nicht aus signal_ts, um Zero-Duration Orders an Sessiongrenzen zu verhindern.
- Wenn `valid_from` außerhalb Session liegt → Order wird verworfen (reject).

Policies:
- `session_end`
- `fixed_minutes` (clamped auf session_end)
- `one_bar`

## OCO (Replay Engine)
Wenn ein Order einer OCO-Gruppe filled:
- alle anderen Orders dieser OCO-Gruppe werden sofort gecancelt
- Event wird geloggt

## Trailing Stop (optional)
- Default: OFF (`trailing_enabled=false`)
- Trigger bei `progress >= trailing_trigger_tp_pct`
  - LONG nutzt `bar.high`
  - SHORT nutzt `bar.low`
- Apply: next_bar
- SL bewegt sich nur in Profit-Richtung.

## Tracing / Reject Reasons
Deterministische Reject Reasons (minimal):
- naive_timestamp
- out_of_session
- mother_bar_outside_session
- mother_bar_too_small
- max_trades_reached
- invalid_validity_window

## Golden Acceptance Checks
- HOOD 45d M5:
  - Trades nur 15–17 Berlin
  - 1–2 Trades/Tag
  - Fills > 0, keine Zero-Validity Orders
- TSLA 20d M5:
  - filled_orders > 0 mit session_end Validity
- diagnostics.json enthält strategy_policy
- keine inside_bar_v2 Referenzen im Codebase
