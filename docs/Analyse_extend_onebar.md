# Exit-Strategie Analyse: Parametrisierung & Erweiterung

**Datum**: 2026-01-02  
**Scope**: Order Validity / Exit Strategy Mechanik  
**Ziel**: Vollständige Analyse der aktuellen "fixed_bars" Implementierung + Entwurf für 3 zusätzliche Optionen

---

## Executive Summary

**Aktuelle Situation**:
- `order_validity_policy` ist bereits **parametrisiert** mit 3 Optionen: `fixed_bars`, `session_end`, `fixed_minutes`
- `fixed_bars` ist **vollständig implementiert** in `trade/validity.py` (Lines 93-97)
- Exit erfolgt in `axiom_bt/engines/replay_engine.py::_exit_after_entry` über `valid_until` Parameter

**Kritisches Architekturfinding**:
- ⚠️ **Module-Coupling**: `trade/validity.py` (Framework-Level) importiert `SessionFilter` aus `strategies/inside_bar/config.py` (Strategy-Level)
- Dies verletzt Separation of Concerns und macht Validity-Modul abhängig von einer spezifischen Strategie

**User-Request-Optionen**:
1. ✅ **fixed_bars** (Status: IMPLEMENTED) - Order expires after 1 bar  
2. ⚠️ **minute-based** (Status: IMPLEMENTED als `fixed_minutes`, aber UI/Doku nennt es anders)
3. ✅ **session-end** (Status: IMPLEMENTED)
4. ❓ **EOD** (Status: UNKLAR - ist das "end of data" oder "end of trading day"?)

---

## 1. Aktuelle Implementierung (Status Quo)

### 1.1 Order Validity Flow (Data Flow Diagram)

```
Signal Generation (Strategy)
    ↓ signal_ts, params
InsideBar.generate_signals()
    ↓ RawSignal objects
OrdersBuilder.signals_to_orders()
    ↓ calls
trade/validity.calculate_validity_window()
    ├─→ Input: signal_ts, timeframe_minutes, session_filter, validity_policy
    ├─→ Calculates: (valid_from, valid_to)  
    └─→ Output: orders.csv with valid_from/valid_to columns
        ↓
axiom_bt/engines/replay_engine.simulate_insidebar_from_orders()
    ├─→ Reads orders.csv
    ├─→ Calls _first_touch_entry(valid_from)
    └─→ Calls _exit_after_entry(entry_ts, valid_until=valid_to)
        ├─→ Iterates bars between entry_ts and valid_until
        ├─→ Checks SL/TP each bar
        └─→ If valid_until reached without SL/TP hit:
            └─→ EXIT at last_close with reason "EOD"
```

**Kritischer Punkt**: `valid_until` in `_exit_after_entry` steuert WIE LANGE nach Entry auf Exit-Kriterien geprüft wird.

### 1.2 Implementierte Policies (Code-verifiziert)

#### Policy 1: `fixed_bars` ✅

**Location**: `trade/validity.py` lines 93-97

```python
if validity_policy == "fixed_bars":
    # Order valid for one bar duration
    # NOTE: Uses ONLY timeframe_minutes; validity_minutes parameter is IGNORED
    valid_to = valid_from + timedelta(minutes=timeframe_minutes)
```

**Semantik**:
- Order gültig für **genau 1 Bar** (z.B. 5 Minuten bei M5)
- valid_from → valid_from + timeframe_minutes
- `validity_minutes` Parameter wird **ignoriert**

**Beispiel** (M5 Timeframe):
- Signal at 15:30
- valid_from_policy="signal_ts" → valid_from = 15:30
- valid_to = 15:30 + 5min = 15:35
- **Window**: 5 Minuten

**Replay-Verhalten**:
- Entry prüfung: Bar 15:30 (0 oder 1 Fill möglich)
- Exit prüfung: Bars von Entry-Bar bis 15:35 (maximal 2 Bars: Entry-Bar + nächste Bar)
- Wenn kein SL/TP hit bis 15:35 → Exit at close of 15:35 bar with reason "EOD"

---

#### Policy 2: `session_end` ✅

**Location**: `trade/validity.py` lines 99-128

```python
elif validity_policy == "session_end":
    session_end = session_filter.get_session_end(valid_from, session_timezone)
    if session_end is None:
        raise ValueError(...)  # valid_from outside session
    valid_to = session_end
    if valid_to <= valid_from:
        raise ValueError(...)  # zero-duration prevention
```

**Semantik**:
- Order gültig **bis Session-Ende**
- Session-Ende wird von `SessionFilter` bestimmt (InsideBar: 16:00 oder 17:00 Berlin)
- **CRITICAL**: session_end berechnet aus `valid_from`, NICHT aus `signal_ts` (verhindert zero-duration bei next_bar policy)

**Beispiel** (Session 15:00-16:00):
- Signal at 15:30
- valid_from="signal_ts" → valid_from = 15:30
- session_end = 16:00
- **Window**: 30 Minuten

**Replay-Verhalten**:
- Entry prüfung: ab 15:30
- Exit prüfung: Bars von Entry bis 16:00 (bis zu 6 Bars bei M5)
- Wenn kein SL/TP hit bis 16:00 → Exit at close of 16:00 bar (letzter Bar in Window)

---

#### Policy 3: `fixed_minutes` ✅

**Location**: `trade/validity.py` lines 130-142

```python
elif validity_policy == "fixed_minutes":
    valid_to = valid_from + timedelta(minutes=validity_minutes)
    
    # Optional: Clamp to session end
    session_end = session_filter.get_session_end(valid_from, session_timezone)
    if session_end and valid_to > session_end:
        valid_to = session_end  # Clamp to session boundary
```

**Semantik**:
- Order gültig für **feste Anzahl Minuten** (`validity_minutes` Parameter)
- Wird **geclampt** auf session_end wenn valid_to über Session-Grenze hinausgeht

**Beispiel** (validity_minutes=30, Session 15:00-16:00):
- Signal at 15:30
- valid_from = 15:30
- valid_to = 15:30 + 30min = 16:00
- session_end = 16:00 → kein Clamp nötig
- **Window**: 30 Minuten

**Beispiel mit Clamp**:
- Signal at 15:45
- valid_from = 15:45
- valid_to = 15:45 + 30min = 16:15
- session_end = 16:00 → geclampt!
- **Finale valid_to**: 16:00
- **Window**: 15 Minuten (statt 30)

---

### 1.3 Exit-Mechanik in replay_engine.py

**Function**: `_exit_after_entry(df, side, entry_ts, stop_loss, take_profit, valid_until)`

**Location**: `replay_engine.py` lines 79-111

**Ablauf**:
1. **Window definieren**: `df.loc[(df.index >= entry_ts) & (df.index <= valid_until)]`
2. **Iteriere Bars** im Window:
   - Prüfe SL hit: `low <= stop_loss` (BUY) oder `high >= stop_loss` (SELL)
   - Prüfe TP hit: `high >= take_profit` (BUY) oder `low <= take_profit` (SELL)
   - Wenn SL oder TP getroffen → **sofort returnen** mit (ts, price, reason)
3. **Falls kein SL/TP** bis `valid_until`:
   - Nehme **letzten Bar** im Window: `last_ts = window.index[-1]`
   - Exit at **close** of last bar: `last_close = window.iloc[-1]["Close"]`
   - Return `(last_ts, last_close, "EOD")`

**Interpretation "EOD"**:
- `"EOD"` = **End Of Data** (oder End Of Duration?)
- Wird gesetzt wenn `valid_until` erreicht ist **ohne** dass SL/TP getroffen wurde
- Ist **nicht** zwangsläufig "End Of Trading Day" sondern "Ende des Validity Windows"

---

## 2. Architektur-Probleme (Coupling Issues)

### 2.1 CRITICAL: SessionFilter Coupling

**Problem**: `trade/validity.py` line 15

```python
from strategies.inside_bar.config import SessionFilter
```

**Was ist falsch?**:
- `trade/validity.py` ist ein **Framework-Level** Modul (unter `src/trade/`)
- `strategies/inside_bar/config.py` ist ein **Strategy-Level** Modul
- **Framework sollte NICHT von spezifischen Strategien abhängen**

**Impact**:
- Validity-Berechnung funktioniert nur für InsideBar-Strategie
- Andere Strategien (z.B. DAX, Rudometkin) können `calculate_validity_window()` nicht nutzen **OHNE InsideBar zu installieren**
- Verletzt Separation of Concerns

**Beweis für Problem**:
```python
# In trade/validity.py:
def calculate_validity_window(
    ...
    session_filter: SessionFilter,  # ← Typ-Annotation ist InsideBar-spezifisch!
    ...
):
    session_end = session_filter.get_session_end(valid_from, session_timezone)
```

**Wie wurde das ursprünglich gedacht?**:
- `SessionFilter` sollte wahrscheinlich ein **Protokoll/Interface** sein (nicht eine konkrete Klasse aus einer Strategie)
- Jede Strategie implementiert ihr eigenes `SessionFilter`
- `trade/validity.py` arbeitet gegen das Interface

**Warum ist das jetzt gekoppelt?**:
- `SessionFilter` ist eine **konkrete Implementierung** in `strategies/inside_bar/config.py`
- Nicht als ABC oder Protocol definiert
- Framework importiert konkreten Strategy-Code

---

### 2.2 Weitere Coupling-Punkte

#### A) orders_builder.py → Strategie-Parameter

**File**: `trade/orders_builder.py` lines 86-87

```python
"order_validity_policy",
strategy_params.get("expire_policy", "session_end"),
```

**Problem**:
- `orders_builder` erwartet Strategy-Parameter mit spezifischen Keys
- Keine klare Schnittstelle (Interface) zwischen Framework und Strategie

**Impact**: MITTEL (akzeptabel, da strategies Dictionary übergeben können)

---



```python
"order_validity_policy": strategy_params.get("order_validity_policy", "session_end"),
```

**Problem**:
- `axiom_bt` (Backtest-Engine) kennt **default values** für Strategy-Parameter
- Sollte eigentlich Strategy-Responsibility sein

**Impact**: NIEDRIG (nur Default-Value, nicht kritisch)

---

### 2.3 Verantwortlichkeiten-Matrix (Wer macht was?)

| Aufgabe | Aktuell | Sollte sein |
|---------|---------|-------------|
| **Validity Policy definieren** | Strategy (config.py) | ✅ Korrekt: Strategy |
| **Validity Window berechnen** | Framework (validity.py) | ✅ Korrekt: Framework |
| **Session-Ende bestimmen** | Strategy (SessionFilter) | ⚠️ Sollte: Framework-Interface |
| **Exit bei valid_until** | Engine (replay_engine) | ✅ Korrekt: Engine |
| **Default Policy setzen** | Strategy + Engine | ⚠️ Sollte: NUR Strategy |

**Fazit**: 2 von 5 Verantwortlichkeiten sind falsch assigned → **Architektur-Refactoring empfohlen**

---

## 3. User-Request: Neue Optionen Analyse

### 3.1 Option 1: "fixed_bars" - STATUS: ✅ VOLLSTÄNDIG IMPLEMENTIERT

**User-Request**: "aktuelle Implementierung"

**Antwort**: Bereits vollständig implementiert und funktionsfähig.

**Code-Location**: `trade/validity.py` lines 93-97

**Keine Änderungen nötig**.

---

### 3.2 Option 2: "minute-based" - STATUS: ⚠️ IMPLEMENTIERT ALS "fixed_minutes"

**User-Request**: "to be done"

**Antwort**: **Bereits implementiert**, aber unter anderem Namen: `fixed_minutes`

**Semantik-Vergleich**:

| User-Name | Code-Name | Bedeutung |
|-----------|-----------|-----------|
| "minute-based" | "fixed_minutes" | Order gültig für N Minuten |

**Hypothese**: User meint wahrscheinlich das gleiche wie `fixed_minutes`.

**Falls NICHT das gleiche gemeint**:
- Bitte User um Klarstellung: Was ist der Unterschied zwischen "minute-based" und "fixed_minutes"?
- Mögliche alternative Interpretationen:
  - "minute-based" = Exit EXACTLY nach N Minuten (ohne Session-Clamp)?
  - "minute-based" = Granularität auf Minuten-Ebene statt Bar-Ebene?

**Recommendation**: User-Klarstellung erforderlich vor Implementierung.

---

### 3.3 Option 3: "end of session window" - STATUS: ✅ IMPLEMENTIERT ALS "session_end"

**User-Request**: "to be done"

**Antwort**: **Bereits vollständig implementiert** als `session_end`.

**Code-Location**: `trade/validity.py` lines 99-128

**Semantik-Vergleich**:

| User-Name | Code-Name | Bedeutung |
|-----------|-----------|-----------|
| "end of session window" | "session_end" | Order gültig bis Session-Ende |

**Keine Änderungen nötig** (außer evt. Umbenennung für Konsistenz).

---

### 3.4 Option 4: "EOD" - STATUS: ❓ UNKLAR

**User-Request**: "to be done"

**Mehrdeutigkeitsproblem**:

"EOD" kann bedeuten:
1. **End Of (Trading) Day** - z.B. 16:00 ET für US-Market RTH
2. **End Of Data** - wie aktuell in replay_engine als Fallback-Reason verwendet
3. **End Of available Data** - letzte verfügbare Bar im Backtest

**Aktuelle Verwendung**:
- `_exit_after_entry` returned `"EOD"` als **exit_reason** wenn `valid_until` erreicht ohne SL/TP hit
- Bedeutet dort: "Order expired" (= End Of Duration)

**Fragen an User**:
1. Soll EOD eine **neue Validity Policy** sein (analog zu session_end)?
2. Falls ja: Was ist die Definition?
   - **Definition A**: Order gültig bis "End of Trading Day" (z.B. 16:00 ET für US, 17:30 CET für EUR)?
   - **Definition B**: Order gültig bis "end of available backtest data"?
   - **Definition C**: Etwas anderes?

**Hypothese** (am wahrscheinlichsten):
- User meint **Definition A**: Order bis End Of Trading Day (Market Close)
- Für US equities: 16:00 ET (= RTH Ende)
- Für InsideBar (Europe/Berlin Timezone): 17:30 Berlin? (XETRA Close)

**Unterschied zu `session_end`**:
- `session_end` = Ende des **aktuellen Session Window** (z.B. 16:00 bei Session "15:00-16:00")
- `EOD` = Ende des **Trading Day** (unabhängig von Session Windows)

**Beispiel-Szenario**:
- InsideBar hat 2 Sessions: 15:00-16:00 und 16:00-17:00
- Signal at 15:30 in Session 1
- `session_end` Policy → valid_to = 16:00 (Ende Session 1)
- `EOD` Policy → valid_to = 17:00 (Ende Session 2 = Ende des Trading Day)

**Recommendation**: User-Klarstellung KRITISCH erforderlich.

---

## 4. Constraints & Edge Cases

### 4.1 Mehrere Positionen bei aufeinanderfolgenden Signalen

**Szenario**:
- Signal 1 at 15:30 → Entry at 15:35, Policy `session_end` (valid_to = 16:00)
- Signal 2 at 15:40 → Entry at 15:45, Policy `session_end` (valid_to = 16:00)

**Frage**: Sind **2 gleichzeitige Positionen** möglich?

**Aktuelle Implementierung** (geprüft in `replay_engine.py` lines 290-330):
```python
for oco_group, oco_orders in group.groupby("oco_group"):
    for _, row in oco_orders.iterrows():
        # Entry logic
        entry_ts, entry_price = _first_touch_entry(...)
        if entry_ts is not None:
            # Exit logic
            exit_ts, exit_price, exit_reason = _exit_after_entry(...)
            # Record fill
            filled.append(...)
            # OCO cancel logic
            if oco_group and oco_group != "":
                for other_idx in oco_orders.index:
                    if other_idx != row_idx and other_idx not in filled_indices:
                        filled_indices.append(other_idx)  # Mark as cancelled
```

**Antwort**: **JA, mehrere Positionen sind möglich** (wenn nicht in selber OCO-Gruppe).

**Mechanik**:
- InsideBar-Strategie hat **Max 1 Trade per Session** constraint
- Dies wird in `generate_signals()` enforced (Strategy-Level)
- ABER: In Replay-Engine gibt es **KEINE** globale Position-Limit-Prüfung
- Wenn 2 Signale in verschiedenen Sessions generiert werden und mit session_end Policy beide bis 16:00 gültig sind → 2 gleichzeitige Positionen **theoretisch möglich**

**InsideBar-Specifics**:
- Session 1: 15:00-16:00
- Session 2: 16:00-17:00
- Max 1 Trade per Session enforced in Strategy
- Signal aus Session 1 kann Entry haben der bis in Session 2 reicht
- Signal aus Session 2 kann zusätzlich ein Entry triggern

**Beispiel**:
- Session 1 Signal at 15:55 → Entry at 15:56, `session_end` → valid_to = 16:00 (Session 1 Ende)
- Kein SL/TP bis 16:00 → **Position bleibt offen** (Exit erst bei SL/TP oder am Ende des validity window)
- **WAIT**: replay_engine macht **Exit at valid_until** mit "EOD" reason!
- Also: Position aus Session 1 wird **closed at 16:00**
- Session 2 Signal at 16:05 → Entry at 16:06 → **neue Position**

**KORREKTUR**: Mit aktueller Implementierung sind **KEINE 2 gleichzeitigen Positionen möglich**, weil:
- Exit erfolgt spätestens am Ende des validity window (valid_until)
- valid_until für Session 1 Signal = Session 1 Ende = 16:00
- Session 2 beginnt bei 16:00
- Keine Überlappung

**ABER**: Mit EOD Policy (falls bis Trading Day Ende):
- Session 1 Signal at 15:30, `policy=EOD` → valid_until = 17:00 (Trading Day Ende)
- Session 2 Signal at 16:05, `policy=EOD` → valid_until = 17:00
- Beide könnten **gleichzeitig offen** sein von 16:05 bis 17:00!

**Constraint**: **Mit EOD Policy sind mehrere gleichzeitige Positionen möglich**.

---

### 4.2 Timing & Determinismus

**Constraint**: ReplayEngine arbeitet **bar-basiert** (nicht tick-basiert).

**Impact**:
- Exit timing is **Präzision = 1 Bar** (z.B. ±5 Minuten bei M5)
- Intra-Bar Fill-Reihenfolge ist **nicht deterministisch** (SL vs TP Priority-Problem bereits dokumentiert)

**Keine Änderung durch neue Policies** - Problem bleibt bestehen.

---

### 4.3 Timezone-Handhabung

**Constraint**: Alle Timestamps **müssen timezone-aware** sein.

**Implementierung** (validiert in `validity.py` lines 75-79):
```python
if signal_ts.tz is None:
    raise ValueError(f"signal_ts must be timezone-aware: {signal_ts}...")
```

**InsideBar-Specifics**:
- Session timezone: `Europe/Berlin`
- Market data timezone: `America/New_York` (wenn US equities)
- Conversion erfolgt in SessionFilter

**Constraint für neue Policies**: **EOD muss timezone-aware sein**.
- Frage: EOD in welcher Timezone?
  - Market timezone (America/New_York für US)?
  - Session timezone (Europe/Berlin für InsideBar)?

---

### 4.4 RTH vs Extended Hours

**Constraint**: Backtests nutzen **RTH-only data** (09:30-16:00 ET für US).

**Aktuelle Policies**:
- Alle arbeiten innerhalb RTH (weil Sessions innerhalb RTH definiert sind)

**EOD Policy**:
- Falls "EOD = 16:00 ET", dann **aligned mit RTH Ende** ✅
- Falls "EOD = after-hours Ende" (z.B. 20:00 ET), dann **outside RTH** ❌
- **Daten nicht verfügbar** für after-hours

**Constraint**: **EOD MUSS innerhalb RTH liegen** (oder separate extended-hours data nötig).

---

## 5. Kritische Iteration - Hinterfragung

### 5.1 Sind die Namen konsistent?

**Problem**:
- Code nennt es: `fixed_bars`, `session_end`, `fixed_minutes`
- User nennt es: `fixed_bars`, `minute-based`, `end of session window`, `EOD`

**Mapping-Vorschlag**:

| User-Name | Code-Name (aktuell) | Status | Aktion |
|-----------|---------------------|--------|--------|
| `fixed_bars` | `fixed_bars` | ✅ Match | Keine |
| `minute-based` | `fixed_minutes` | ⚠️ Verschieden | Umbenennen oder Klarstellen |
| `end of session window` | `session_end` | ⚠️ Verschieden | Umbenennen oder Klarstellen |
| `EOD` | - | ❌ Nicht impl | Neu implementieren (nach Klärung) |

**Recommendation**: **Konsistente Naming Convention** etablieren.

---

### 5.2 Ist das SessionFilter-Coupling ein Blocker?

**Frage**: Kann man neue Policies implementieren **OHNE** SessionFilter zu refactoren?

**Antwort für fixed_bars**: ✅ Ja (braucht kein SessionFilter)

**Antwort für EOD** (Definition A: Trading Day Ende):
- Braucht **EOD-Zeitpunkt** → ähnlich wie SessionFilter
- Gleiche Coupling-Problem würde auftreten
- **Entweder**:
  - A) EOD hard-coded per Market (z.B. "16:00" für US, "17:30" für EUR) → **kein SessionFilter nötig**
  - B) EOD über Interface (analog SessionFilter) → **Coupling bleibt**

**Recommendation**: Falls EOD implementiert wird → **nutze Gelegenheit für SessionFilter-Refactoring**.

---

### 5.3 Ist die Valid_Until-Semantik richtig?

**Aktuell**: `_exit_after_entry(valid_until)` bedeutet:
- "Prüfe Bars von entry_ts bis valid_until auf Exit-Kriterien (SL/TP)"
- "Falls kein Kriterium getroffen, exit at close of last bar in window"

**Semantik-Check**:
- ✅ **Korrekt für time-limited orders** (z.B. "Order gültig bis 16:00")
- ❓ **Unklar für "unbegrenzte" Orders** (z.B. "Order bis SL/TP, kein Timeout")

**Frage**: Sollte es eine Policy geben für "**no expiry**" (Good Till Cancelled)?

**Code-Hinweis**: `cli_export_orders.py` line 82 erwähnt `"good_till_cancel"` Option!

```python
parser.add_argument("--expire-policy", choices=["session_end", "good_till_cancel"], ...)
```

**Aber**: Diese Option ist **NICHT** in `validity.py` implementiert.

**Recommendation**: **GTC (Good Till Cancelled) Policy** könnte sinnvoll sein als 5. Option.

---

## 6. Zusammenfassung & Erkenntnisse

### 6.1 Was ist BEREITS implementiert (entgegen User-Annahme)

| User-Request | Code-Status | Name in Code |
|--------------|-------------|--------------|
| minute-based | ✅ Implementiert | `fixed_minutes` |
| end of session window | ✅ Implementiert | `session_end` |
| fixed_bars | ✅ Implementiert | `fixed_bars` |

**→ 3 von 4 Optionen sind bereits fertig!**

---

### 6.2 Was MUSS geklärt werden

1. **"minute-based" vs "fixed_minutes"**: Ist das das gleiche? Falls ja → Dokumentation/UI aktualisieren. Falls nein → Semantik klären.

2. **EOD Definition**: Was bedeutet "EOD"?
   - End of Trading Day? (z.B. 16:00 ET)
   - End of last Session?
   - End of backtest data?

3. **EOD Timezone**: Welche Timezone für EOD?
   - Market timezone (America/New_York)?
   - Session timezone (Europe/Berlin)?
   - Konfigurierbar per Strategie?

---

### 6.3 Architektur-Probleme

| Problem | Severity | Impact | Recommendation |
|---------|----------|--------|----------------|
| **SessionFilter Coupling** | 🔴 HIGH | Framework kann nicht ohne InsideBar-Strategie verwendet werden | Refactor: SessionFilter als Protocol/ABC im Framework |
| **Default Policy in Engine** | 🟡 MEDIUM | Engine kennt Strategy-Defaults | Refactor: Defaults nur in Strategy |
| **Naming Inconsistenz** | 🟡 MEDIUM | User-Doku vs Code-Namen unterschiedlich | Dokumentation + UI angleichen |
| **Missing GTC Policy** | 🟢 LOW | "Good Till Cancel" nicht verfügbar | Optional: Implementieren |

---

### 6.4 Constraint-Matrix

| Constraint | fixed_bars | session_end | fixed_minutes | EOD (proposed) |
|------------|---------|-------------|---------------|----------------|
| **Mehrere Positionen möglich** | Nein* | Nein* | Nein* | **Ja*** |
| **Timezone-aware** | ✅ | ✅ | ✅ | ✅ (required) |
| **RTH-compatible** | ✅ | ✅ | ✅ | ⚠️ (if EOD=16:00) |
| **SessionFilter-frei** | ✅ | ❌ | ❌ | ❌ |
| **Deterministic** | ✅ | ✅ | ✅ | ✅ |

\* Bei InsideBar: Max 1 Trade/Session enforced in Strategy. Bei anderen Strategien ohne dieses Constraint **könnten** mehrere Positionen entstehen mit EOD Policy.

---

## 7. Offene Fragen (MUST-ANSWER vor Implementierung)

### CRITICAL (Blocker)

1. **EOD-Definition**: Was bedeutet "EOD" konkret?
   - Option A: End of Trading Day (Market Close, z.B. 16:00 ET)
   - Option B: End of last Session (Strategy-spezifisch)
   - Option C: End of data (backtest boundary)

2. **"minute-based" Semantik**: Ist das identisch mit `fixed_minutes` oder etwas anderes?

### HIGH (Vor Implementierung klären)

3. **EOD Timezone**: Falls EOD = Market Close, in welcher Timezone?
   - Market-specific (US=ET, EUR=CET)?
   - Strategy-config (parametrisiert)?

4. **SessionFilter Refactoring**: Soll das Coupling jetzt behoben werden oder später?
   - Wenn jetzt: EOD-Implementierung nutzt neues Interface
   - Wenn später: EOD hat gleiches Coupling-Problem

### MEDIUM (Design-Entscheidungen)

5. **Mehrere Positionen bei EOD**: Soll das explizit erlaubt/verboten werden?
   - Falls erlaubt: Position-Tracking in Engine erforderlich?
   - Falls verboten: Wie enforced? (Strategy-Level oder Engine-Level?)

6. **GTC Policy**: Soll "Good Till Cancelled" als 5. Option hinzugefügt werden?

---

**Dokument Ende** - Next: `Implement_extend_onebar.md`
