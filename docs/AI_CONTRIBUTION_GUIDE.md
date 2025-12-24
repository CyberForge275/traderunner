# AI Contribution Guide

Dieser Leitfaden definiert, wie KI-gestützte Änderungen an den Projekten
`traderunner`, `automatictrader-api` und `marketdata-stream` erfolgen dürfen.

Ziel: **Qualität vor Quantität**

- Keine „Quick Fixes“ ohne Kontext.
- Keine schleichende Erosion der Architektur.
- Änderungen sollen reproduzierbar, getestet und nachvollziehbar sein.


## 1. Geltungsbereich

Dieser Guide gilt für **alle** Änderungen, die durch ein AI-Tool (z. B. Antigravity, ChatGPT) vorgeschlagen oder durchgeführt werden:

- Bugfixes
- Refactorings
- neue Features
- Doku-Updates, die Programmverhalten betreffen

Wenn eine Regel kollidiert: **die strengere Regel gewinnt**.


## 2. Grundprinzipien

1. **Verstehen vor Ändern**
   Bevor Code geändert wird:
   - Datei vollständig lesen (nicht nur Diff-Ausschnitt).
   - Nach referenzierten Funktionen, Mappings, Enums, Configs suchen.
   - Invarianten identifizieren (z. B. „jeder `tf-*` Button braucht ein Mapping“).

2. **Single Source of Truth respektieren**
   - Strategien, Timeframes, Pfade, Konfigurationen haben **genau einen** Ursprung.
   - Keine Duplikate in UI, Tests oder Helpers anlegen.
   - Neue Stellen müssen auf bestehende Quellen aufbauen – nicht umgekehrt.

3. **Minimaler, gezielter Diff**
   - Nur das ändern, was für den Fix wirklich nötig ist.
   - Kein unaufgefordertes Refactoring, kein massives Umformatieren ganzer Dateien.

4. **Keine neuen „Abkürzungen“**
   - Kein Hard-Coding von Pfaden, Credentials, Magic Strings.
   - Keine Strategy-Logik im UI-Layer.
   - Keine neuen globalen States ohne explizite Begründung.

5. **Tests zuerst denken, dann Code**
   - Was soll nach der Änderung garantiert sein?
   - Wie lässt sich das in einem Test ausdrücken?
   - Danach erst Code anfassen.


## 3. Workflow für JEDE AI-Änderung

### Schritt 1: Kontext sammeln

Vor einem Fix:

- Alle relevanten Dateien öffnen:
  - die Datei mit dem Fehler
  - direkt verknüpfte Layouts/Configs/Services
- Referenzen suchen:
  - Beispiel: bei `timeframe_map` → alle Vorkommen von `tf-m1`, `tf-m5`, … im Projekt.

Frage, die beantwortet sein muss:
> „Welche anderen Stellen hängen von dieser Änderung ab?“


### Schritt 2: Invarianten definieren

Vor dem Patch 2–5 Invarianten notieren, z. B.:

- „Jeder Button mit ID `tf-*` muss im Timeframe-Registry vorkommen.“
- „Strategien, die im UI auswählbar sind, müssen im StrategyCatalog existieren.“
- „Core-Services dürfen keine absoluten Pfade enthalten.“

Diese Invarianten sind die **Qualitätsanker** für den Rest des Workflows.


### Schritt 3: Änderung planen (kurzer Plan)

Kurz schriftlich festhalten:

- Welche Zeilen/Funktionen werden angepasst?
- Welche Alternativen wurden erwogen?
- Warum ist diese Lösung **minimal** und **sicher**?

Wenn der Plan größer ist als ein paar Sätze → als eigenes Ticket/Epic behandeln, nicht „nebenbei fixen“.


### Schritt 4: Patch implementieren (minimal)

- Nur die Bereiche anpassen, die im Plan genannt sind.
- Keine zusätzlichen „Nice to have“-Änderungen in derselben Commit-Einheit.
- Keine neuen Abhängigkeiten ohne Begründung + Doku.

Spezialfall: wenn beim Fix tiefere Architekturprobleme sichtbar werden:
- **Fix klein halten**,
- Problem in TODO / Ticket notieren,
- später gezielt angehen (kein „Architektur-Drive-By“).


### Schritt 5: Checks & Tests

Nach jedem AI-Patch:

- Statische Checks (sofern vorhanden):
  - Linter / Format (ruff, black, o. ä.)
  - Typ-Check (mypy o. ä.)
- Tests:
  - Mindestens die relevanten Unit-Tests für das betroffene Modul.
  - Wenn ein zentraler Entry-Point betroffen ist, auch ein schneller Integrationstest.

Fehlt ein Test für die definierte Invariante:
- neuen Test anlegen (kurz, fokussiert),
- erst dann patch als „fertig“ betrachten.


### Schritt 6: Änderung dokumentieren

Im Commit / PR / Kommentar:

- Problem in 1–2 Sätzen beschreiben.
- Lösung in 1–2 Sätzen beschreiben.
- Erwähnen, welche Invarianten geprüft und welche Tests gelaufen sind.


## 4. Spezielle Regeln nach Änderungstyp

### 4.1 Bugfixes

- **Keine** stillen Funktionsänderungen.
- Parameter- oder Return-Typen nur ändern, wenn Bug andernfalls nicht lösbar.
- Wenn Verhalten sich ändert:
  - **immer** neuen oder angepassten Test hinzufügen.
- Kein Bugfix ohne Root-Cause-Erklärung (mind. 1–2 Sätze).

### 4.2 Refactorings

Refactorings sind nur erlaubt, wenn:

- sie in einem eigenen Commit oder PR stehen,
- sie begrenzt sind (z. B. nur ein Modul oder ein klar umrissener Teil),
- sie die bestehenden Invarianten vollständig erhalten (Tests müssen grün bleiben),
- sie die Komplexität messbar reduzieren (z. B. weniger Codepfade, bessere Separation).

Kein Refactoring „im Vorbeigehen“ beim Bugfix – außer absolut notwendig.


### 4.3 Neue Features

Für neue Features gilt zusätzlich:

- Feature darf bestehende Architektur nicht brechen:
  - keine neuen Cross-Layer-Abhängigkeiten
  - keine Strategy-Logik in Dashboard-Callbacks
- Feature muss:
  - in Doku kurz beschrieben werden (User-Sicht),
  - in Tests zumindest Happy Path abdecken,
  - in Config/Settings sauber verankert sein (keine Hard-coded Pfade).


## 5. Architektur-Regeln (nicht verhandelbar)

### 5.1 Layers & Boundaries

- Core/Engine/Strategies:
  - keine UI-Abhängigkeiten (Plotly, Dash, Streamlit etc.).
- Dashboard (`trading_dashboard`):
  - UI-Layout, User-Interaktion, Orchestrierung.
  - Business-Logik gehört in `services`, nicht in `callbacks` oder `layouts`.
- Marketdata-Stream:
  - kümmert sich nur um Daten-Ingestion und -Bereitstellung, nicht um Strategie-Logik.

Verstöße gegen diese Schichten gelten als **Major Issue**.


### 5.2 Strategien & Konfiguration

- Strategien werden **nur** im zentralen StrategyCatalog definiert:
  - StrategyID, impl_version, Capabilities, Config-Schema, Defaults.
- UI, Backtests, marketdata-stream greifen **nur über den Catalog** auf Strategien zu.
- Kein `if strategy_name == "insidebar_..."` in Services/Adapter:
  - Verhalten wird über Capabilities und Config gesteuert, nicht über Namen.
- Strategy-Profile (z. B. „default“, „aggressive“) werden versioniert und nicht in Code dupliziert.


### 5.3 Konfiguration & Pfade

- Keine absoluten Pfade (`/home/...`, `/opt/...`) in Core/Services.
- Pfade, Datenbanken und externe Endpunkte kommen immer aus:
  - einem Settings-Objekt oder
  - einem zentralen Config-Mechanismus.
- Adapter (z. B. Pre-PaperTrade) bekommen Repositories/Loader **injiziert**, sie erzeugen keine Pfade selbst.


### 5.4 Visualisierung (Plotly & Co.)

- Plotly (oder andere Chart-Frameworks) sind auf dedizierte Pakete beschränkt, z. B.:
  - `visualization/plotly/…`
- UI-Callbacks:
  - sammeln Daten,
  - bereiten Config vor,
  - rufen `build_*_chart()` auf,
  - verändern keine Plot-Details direkt.

Ziel: Austauschbarkeit und Testbarkeit der Visualisierung.


## 6. Qualität > Quantität

- Mehr Code ist **kein** Erfolgskriterium.
- „Gute“ Beiträge:
  - reduzieren Komplexität,
  - stärken Invarianten,
  - verbessern Tests & Doku.
- „Schlechte“ Beiträge:
  - erzeugen neue Sonderfälle,
  - duplizieren Logik,
  - schwächen bestehende Architektur-Regeln.

Im Zweifel lieber **eine kleine, saubere Änderung** als viele halbgare.


## 7. Wann AI „Stopp“ sagen sollte

Die AI sollte Änderungen **ablehnen oder vertagen**, wenn:

- der Kontext unklar ist (z. B. fehlende Infos zu externen Abhängigkeiten),
- das Problem offensichtlich tiefer liegt (Architektur-Thema statt Bugfix),
- ein Fix mehr als einen klar abgegrenzten Bereich berührt,
- Tests oder CI-Infrastruktur fehlen, um die Auswirkungen zu prüfen.

In solchen Fällen:
- Problem beschreiben,
- Risiken benennen,
- Vorschlag für manuelle oder größere Refactoring-Story machen.


## 8. Weiterentwicklung dieses Guides

Dieser Guide ist ein **lebendes Dokument**.

Nach echten „Findings“ (Fehlern, die durch AI-Änderungen entstanden sind):

- den Vorfall kurz beschreiben (anonymisiert),
- die verletzte Regel identifizieren,
- ggf. neue Regel/Invariante ergänzen oder präzisieren.

Ziel: Mit jedem Vorfall wird der Guide ein Stück „bulletproof-er“.
