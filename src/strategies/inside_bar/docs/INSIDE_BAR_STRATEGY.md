# InsideBar Strategy – SSOT Contract

Stand: 2025-12-18
SSOT: `src/strategies/inside_bar/`
Ziel: deterministischer, auditierbarer M5-Intraday Backtest + Live-Kompatibilität

## 1. Hintergrund: Warum November funktionierte und TSLA aktuell nicht
### November (HOOD) – Erfolgsfaktor
Die 1–2 Trades/Tag kamen NICHT durch “max-trades” in der Strategie zustande, sondern durch:
- Europe/Berlin Sessionfenster (15–16, 16–17)
- Orders mit Validity bis Session-Ende (typisch 10–60 Minuten)
- Dadurch konnten STOP Orders im Bar-basierten Replay überhaupt gefillt werden.

### TSLA (aktuell) – 0 Fills Root Cause
orders.csv hatte `valid_from == valid_to` (0 Minuten).
Im Bar-Replay ist eine 0-Duration Order nicht “aktiv” in einer Bar → Fill ist praktisch unmöglich.

**Fix-Contract:** default `order_validity_policy = session_end` und `valid_to > valid_from`.

## 2. Handelszeiten (Always-On)
- session_timezone: `Europe/Berlin` (DST-sicher)
2. **Sessions**: Parameterized via `session_windows` (production default: `["15:00-16:00", "16:00-17:00"]` Berlin time)r ist immer aktiv (nie None / nie “aus”)

## 3. Setup: Inside Bar Definition
Inside Bar Candle i relativ zu Candle i-1:
- high[i] <= high[i-1]
- low[i]  >= low[i-1]
Mother Bar = Candle i-1

## 4. Entry (final festgelegt)
Default: `entry_level_mode = mother_bar`
- LONG Entry: Mother High
- SHORT Entry: Mother Low
Optional (nur via Switch): `inside_bar`

## 5. Stop Loss + Cap
SL initial:
- LONG: SL = Mother Low
- SHORT: SL = Mother High

SL Cap:
- stop_distance_cap_ticks default = 40
- tick_size default = 0.01
MaxRisk = 40 * 0.01 = 0.40 (Price Units)
Wenn Risk > MaxRisk → SL Richtung Entry verschieben (Risk = MaxRisk)

## 6. Take Profit
TP via Risk/Reward Ratio:
- LONG: TP = Entry + RRR * Risk
- SHORT: TP = Entry - RRR * Risk

## 7. Sessions: max 1 Trade pro Session
Default: `max_trades_per_session = 1`
Key: (local_date_in_session_tz, session_index)
Ergebnis: max 2 Trades pro Tag (2 Sessions)

## 8. Edge Case: First Candle in Session ist Inside Bar
Wenn die erste Candle einer Session eine Inside Bar ist, wird dieser Setup verworfen,
weil die Mother Bar außerhalb der Session liegt.

Reject Reason: `first_candle_inside_bar`

## 9. Order Validity (kritisch)
Default:
- valid_from_policy = signal_ts
- order_validity_policy = session_end

Regeln:
- valid_from = signal_ts (oder next_bar)
- valid_to = session_end (oder fixed_minutes, clamp to session_end)
- Wenn valid_to <= valid_from → keine Order (reject invalid_validity_window)

## 10. OCO (Replay Enforcement)
Wenn eine Order einer OCO-Gruppe gefillt wird, werden alle anderen Orders derselben OCO-Gruppe gecancelt.

## 11. Trailing Stop (konfigurierbar)
Trigger:
- wenn Kurs 70% des TP-Wegs erreicht → trailing armed

Apply Mode:
- `next_bar` (final festgelegt): SL-Update erst ab nächster Bar

New SL:
- LONG: SL_new = Entry - initial_risk * trailing_risk_remaining_pct
- SHORT: SL_new = Entry + initial_risk * trailing_risk_remaining_pct
SL bewegt sich nur in Profit-Richtung.
- trailing_enabled: default OFF

## 12. Audit-Artefakte
Always-on:
- diagnostics.json (data sanity + warmup + strategy_policy)
- run_steps.jsonl (inkl. strategy_policy)

Debug-only:
- debug/inside_bar_trace.jsonl
- debug/inside_bar_summary.json
- debug/orders_debug.jsonl

## 13. Golden Runs
- HOOD 45d M5: erwartet ~1–2 Trades/Tag, hohe Fillrate, Trades 15–17 Berlin
- TSLA 20d M5: erwartet filled_orders > 0 (nicht mehr 0%)
