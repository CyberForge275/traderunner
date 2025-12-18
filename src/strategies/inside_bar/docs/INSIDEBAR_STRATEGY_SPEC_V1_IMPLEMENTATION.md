# InsideBar Strategy (SSOT) – Spec-Implementierung

## Ziel
Diese Dokumentation beschreibt die *finale* InsideBar-Strategie als Single Source of Truth (SSOT) und die verbindlichen Defaults für Backtest und Live.

## Standardannahmen
- Timeframe: M5
- Timezone für Session-Auswertung: Europe/Berlin (inkl. DST/CET/CEST automatisch)
- Sessions (immer aktiv, aber konfigurierbar):
  - 15:00–16:00
  - 16:00–17:00
- Entry-Level Mode: mother_bar (fix)
- Trailing: Default OFF
- Max Trades pro Session: 1

## Kerndefinitionen
### Inside Bar
Eine Kerze ist Inside Bar (IB), wenn:
- IB.high <= Mother.high
- IB.low  >= Mother.low
(Mode "inclusive"; strict wäre < und >)

### Entry (mother_bar)
- LONG Entry: mother_high
- SHORT Entry: mother_low

### Stop Loss (Mother Bar)
- LONG SL: mother_low
- SHORT SL: mother_high

### SL Cap (Ticks)
Die SL-Distanz wird begrenzt:
- max_risk = stop_distance_cap_ticks * tick_size
Wenn risk > max_risk:
- SL wird so verschoben, dass risk == max_risk
- TP wird anhand des gecappten Risikos neu berechnet.

### Take Profit (RRR)
TP basiert auf Risk-Reward-Ratio:
- LONG: TP = entry + risk * RRR
- SHORT: TP = entry - risk * RRR

## Session-Regeln (verbindlich)
- Signals/Orders dürfen nur innerhalb der Sessions entstehen (Berlin-Zeit).
- Pro Session maximal 1 Trade (Default).
- Sonderfall (Mother Bar außerhalb Session):
  - Wenn die erste Kerze der Session eine Inside Bar ist, liegt die Mother Bar vor Sessionstart.
  - In diesem Fall wird kein Trade erzeugt (reject: mother_bar_outside_session).

## Order Validity (kritisch für Replay-Fills)
Replay-Simulation arbeitet bar-basiert (M5). Eine Order muss eine *echte* Gültigkeitsdauer haben.
Default:
- order_validity_policy = session_end
- valid_to = Session-Ende (des passenden Sessionslots)
- valid_to muss > valid_from sein

Alternative Policies:
- fixed_minutes: valid_to = valid_from + N Minuten
- instant: ist nicht 0 Sekunden, sondern mindestens 1 Bar gültig (sonst Zero-Fill)

valid_from_policy:
- signal_ts oder next_bar

## Trailing Stop (optional)
Default: trailing_enabled = False

Wenn enabled:
- Trigger: bei 70% des TP-Wegs
- Neuer SL: entry ± initial_risk * trailing_risk_remaining_pct
- Apply Mode: next_bar (SL gilt erst ab der folgenden Kerze)

## Audit-Artefakte
Immer (auch ohne Debug):
- diagnostics.json (Data sanity + Warmup)

Nur bei Debug:
- inside_bar_trace.jsonl (candle-by-candle decisions)
- inside_bar_summary.json (aggregierte Stats + Reject reasons)
- orders_debug.jsonl (Signal → Order Mapping inkl. Qty)

## Golden Tests
- HOOD November Parity:
  - Trades ausschließlich 15–17 Berlin
  - 1–2 Trades/Tag
  - Fillrate deutlich > 0
- TSLA Replay Fill Sanity:
  - Bei session_end/fixed_minutes müssen Fills möglich sein
