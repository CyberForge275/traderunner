Executive Summary
==================

- Source-Time bleibt UTC, Market-Time pro Exchange/Instrument, Display-Time bleibt Europe/Berlin. Keine naive Datetimes. UTC-Persistenz + Meta (market_tz, display_tz) ist Standard; Market-Zeit wird nur mit klarer Meta gespeichert.
- Sessions sind eindeutig: SessionSpec.mode = MARKET (Default, empfohlen), optional DISPLAY (bewusstes Opt-in). UI zeigt Berlin, Trading rechnet in Market.
- Kernmodelle: InstrumentRegistry (market_tz, calendar_id, tick_size), TimeContext (canonical_tz=UTC, market_tz, display_tz, bar_spec, session_spec), BarSpec (label/closed/origin/offset), SessionSpec (windows, tz, mode), RequestedEndSpec (date-only → interpretiert als market-date, dann zu UTC normiert).
- Zentraler Time-Service (axiom_bt/time/): Parsing EODHD→UTC, Konvertierungen (utc↔market↔display), Session-Resolution, Validity Calculator (one_bar, session_end, fixed_minutes), Bar-Timestamp-Semantik (bar-close), DST-handling inkl. ambiguous times.
- Resampling Standard: resample in market_tz, label=right, closed=right, origin=epoch, offset=0, strikt gegen off_step_count; DST-stabil über tz-aware Index.
- CalendarProvider: Interface für trading day/open/close/early close; minimal stub jetzt, später echte Calendars.
- Architektur-Mapping: IntradayStore/eodhd_fetch resample in market_tz; OrdersBuilder benutzt Time-Service Validity; Strategy nutzt bar-close ts; Replay Engine respektiert validity; FullBacktestRunner löst requested_end via RequestedEndSpec; Dashboard zeigt Display-TZ.
- Migration in 3 Phasen (additiv → tightening → calendar-accurate), mit Tests: DST boundary, Multi-exchange (NYSE vs XETR), requested_end date-only, validity window one_bar, no-naive-datetime.


1) Glossar & Invarianten (SSOT)
-------------------------------

- Source Time: UTC (EODHD liefert UTC + gmtoffset; wir vertrauen nur UTC). Alle Rohdaten in UTC speichern.
- Market Time: Börsenlokal pro Instrument/Exchange (z. B. America/New_York für NYSE/NASDAQ, Europe/Berlin für XETR). Wird durch Registry bestimmt, nicht aus Daten erraten.
- Display Time: Europe/Berlin für UI/Reporting. Reine Präsentation, keine Trading-Logik.
- No-naive-datetime: Alle internen Timestamps sind tz-aware. Naive Werte werden abgelehnt oder sofort lokalisiert mit expliziter TZ.
- Persistenz-Regeln:
  - Empfehlung: Persistiere Zeitachsen in UTC + `meta.market_tz`, `meta.display_tz`.
  - Wenn Market-Zeit persistiert wird, MUSS `meta.market_tz` beigefügt werden; keine gemischten Achsen.
  - Artifacts (csv/json) sollen UTC-Stempel tragen, plus Meta (market_tz, display_tz) im Manifest/diagnostics.


2) Session-Windows Semantik (MUSS eindeutig)
---------------------------------------------

- SessionSpec.mode:
  - MARKET (Default, empfohlen): Fenster werden in market_tz interpretiert; Trading/Validity rechnet in Market-Zeit.
  - DISPLAY (Opt-in): Fenster werden in display_tz interpretiert (nur für spezielle Analysen). Trading sollte das nur mit ausdrücklichem Opt-in nutzen.
- Empfehlung: MARKET als Default für alle Strategien/Orders; DISPLAY nur als bewusste Ausnahme.
- UI in Berlin: Anzeige konvertiert Werte (signals/orders/equity) nach display_tz, ohne die Trading-Logik zu beeinflussen.


3) Core-Datenmodelle (SSOT)
---------------------------

- InstrumentRegistryEntry
  - fields: symbol, exchange, market_tz, calendar_id, tick_size, trading_hours (optional overrides)
  - example: {symbol: "HOOD", exchange: "NASDAQ", market_tz: "America/New_York", calendar_id: "XNYS", tick_size: 0.01}
  - validation: market_tz is tzdb name; tick_size > 0.

- TimeContext
  - fields: canonical_tz (UTC), market_tz, display_tz (default Europe/Berlin), exchange, calendar_id, bar_spec, session_spec
  - example: {canonical_tz: "UTC", market_tz: "America/New_York", display_tz: "Europe/Berlin", bar_spec: BarSpec(M5,...), session_spec: SessionSpec(mode=MARKET, windows=["09:30-16:00"], tz="America/New_York")}
  - validation: canonical_tz == UTC; market_tz/display_tz valid tzdb; bar_spec/session_spec present.

- BarSpec
  - fields: timeframe_minutes (int), label ("right"), closed ("right"), origin ("epoch"), offset (default "0min")
  - example: {tfm:5, label:"right", closed:"right", origin:"epoch", offset:"0min"}
  - validation: tfm>0; label/closed in {left,right}; origin in {start,epoch}.

- SessionSpec
  - fields: windows ["HH:MM-HH:MM"], tz, mode (MARKET|DISPLAY)
  - example: {windows:["09:30-16:00"], tz:"America/New_York", mode:"MARKET"}
  - validation: windows non-empty; tz valid; mode in enum.

- RequestedEndSpec
  - fields: raw (str|date|ts), interpretation ("market_date" default), tz (market_tz), resolved_utc (Timestamp)
  - rule: date-only → interpretiere als market calendar date end-of-day (session close) → konvertiere zu UTC.
  - example: raw="2025-12-17", market_tz=America/New_York → resolved_utc = 2025-12-18T03:59:59Z (bei 16:00 NY).


4) Zentraler Zeit-Service (axiom_bt/time/)
------------------------------------------

Modul-API (Signaturen skizziert):

- parse_eodhd_timestamp(raw: str|int, gmtoffset: int|None) -> pd.Timestamp (UTC)
  - nutzt gmtoffset nur zur Validierung/Logging, primär UTC.

- to_market(ts_utc: pd.Timestamp, market_tz: str) -> pd.Timestamp
- to_display(ts_utc: pd.Timestamp, display_tz: str = "Europe/Berlin") -> pd.Timestamp
- to_utc(ts: pd.Timestamp, from_tz: str) -> pd.Timestamp

- resolve_session(spec: SessionSpec, ts: pd.Timestamp, market_tz: str) -> Tuple[session_start, session_end]
  - nutzt CalendarProvider, fällt zurück auf SessionSpec.windows.

- calculate_validity(signal_ts: pd.Timestamp, bar_spec: BarSpec, session_spec: SessionSpec, policy: str, validity_minutes: int = 60, valid_from_policy: str = "signal_ts") -> Tuple[valid_from, valid_to]
  - policies: one_bar (valid_to = valid_from + tfm), session_end (bis session_end), fixed_minutes (clamp an session_end).
  - garantiert valid_to > valid_from; wirft ValueError sonst.

- bar_timestamp_semantics(bar_ts: pd.Timestamp, bar_spec: BarSpec) -> pd.Timestamp
  - definiert: Signals/Orders verwenden bar-close (label=right/closed=right).

- handle_dst(ts: pd.Timestamp, tz: str, how: Literal["raise","fold_forward"] = "raise") -> pd.Timestamp
  - validiert/ent-ambiguiert.


5) Resampling-Standard (M1→Mx)
-------------------------------

- Resample in market_tz (nicht UTC), um session alignment + DST korrekt zu halten; danach Ergebnis nach UTC persistieren.
- Pandas-Params: `resample(f"{tfm}T", label="right", closed="right", origin="epoch", offset="0min")` auf tz-aware Index (market_tz).
- Steps:
  1) Rohdaten (UTC) → in market_tz konvertieren
  2) resample mit obigen Parametern
  3) zurück nach UTC speichern, Meta: market_tz, bar_spec
- off_step_count vermeiden: Nach resample prüfen, ob (expected_step_seconds, mode_step_seconds, off_step_count==0) sonst warn/error.
- DST: tz-aware Index; pandas handhabt Lapses/Splits korrekt bei label/right wenn in lokaler TZ.


6) CalendarProvider Interface
------------------------------

- class CalendarProvider:
  - is_trading_day(date, calendar_id) -> bool
  - session_open_close(date, calendar_id) -> Tuple[open_ts, close_ts]
  - is_trading_minute(ts, calendar_id) -> bool
- Minimal-Stub: feste RTH pro exchange (z. B. 09:30–16:00 NYSE, 09:00–17:30 XETR), keine Holidays.
- Perspektive: Integration mit pandas_market_calendars oder exchange-calendars; Early Close/ Holidays via calendar_id.


7) Architektur-Mapping (Komponente → Änderung)
-----------------------------------------------

- IntradayStore / eodhd_fetch: Nach Laden UTC→market_tz, resample in market_tz mit BarSpec-Parametern, zurück nach UTC speichern + Meta (market_tz, bar_spec).
- OrdersBuilder: nutzt Time-Service.calculate_validity mit SessionSpec (mode=MARKET default), valid_from_policy, order_validity_policy (one_bar etc.). Kein Fallback auf Market-Close bei one_bar.
- Strategy: signal_ts ist bar-close (label/right). Tracer/Signals in market_tz, persistiert als UTC + Meta.
- Replay Engine: interpretiert valid_from/valid_to in market_tz (oder UTC+meta) via Time-Service; Synthesezeiten ohne now().
- FullBacktestRunner: RequestedEndSpec löst date-only in market date (session close) auf, dann zu UTC; TimeContext wird pro Run gesetzt.
- Dashboard: Anzeige in display_tz (Berlin); server-side Konvertierung via Time-Service.to_display; Diagnostics/report enthalten market_tz + display_tz.


8) Migrationsplan (ohne Breaking Changes)
----------------------------------------

- Phase 1 (additiv, sicher):
  - Add TimeContext, SessionSpec.mode, RequestedEndSpec (nur verdrahten, nicht erzwingen).
  - Time-Service Modul mit Konvertierern + Validity Calculator; OrdersBuilder nutzt es hinter Feature-Flag (default ON für one_bar Fix, sonst identisch).
  - Diagnostics erweitern: speichern market_tz, display_tz, bar_spec, session_spec, requested_end_resolved.
  - DoD: Tests grün, Debug-Runs zeigen unveränderte Ergebnisse außer one_bar-Fix.
  - Risiko: Gering (additiv). Rollback: Flag aus.

- Phase 2 (resampling tightening):
  - Intraday resample explizit mit BarSpec-Parametern; enforce tz-aware; off_step_count check.
  - requested_end date-only → RequestedEndSpec (market close) aktivieren.
  - DoD: M5 parity vs vorher, off_step_count=0, DST-Test grün.
  - Risiko: mögliche leichte Bar-Grenzverschiebung; Rollback: Flag, altes resample beibehalten.

- Phase 3 (calendar accuracy):
  - CalendarProvider Stub → echte Kalender; SessionSpec aus Registry/Calendar ableiten.
  - Early Close/Holidays berücksichtigen in SessionResolution + Validity.
  - DoD: Multi-exchange & Holiday Tests grün; UI zeigt korrekte Handels-/Feiertagsinfo.
  - Risiko: Kalenderdatenfehler; Rollback: Stub wieder aktivieren.


9) Quality Gates & Tests
------------------------

- DST Boundary Test: NYSE M1→M5 über DST-Wechsel; off_step_count==0; session alignment korrekt; validity windows gültig.
- Multi-Exchange Test: NYSE vs XETR (unterschiedliche market_tz, calendars) mit selben UTC-Daten; Sessions korrekt getrennt.
- requested_end date-only: "2025-12-17" → resolved_utc = session_close(market_tz) in UTC; equity/trades vorhanden.
- Validity Window Test: order_validity_policy=one_bar → (valid_to - valid_from) == timeframe_minutes.
- No-Naive-Datetime Test: alle öffentlichen APIs werfen auf naive ts.
- Property-based Idee: für zufällige session_windows und tfm prüfen, dass calculate_validity immer valid_to > valid_from und innerhalb Session (für session_end).


10) Anti-Patterns (nicht wieder tun)
------------------------------------

- Naive Datetimes in Pipelines oder Persistenz.
- Session-Fenster ohne mode/tz; implizit Market-Close bei one_bar.
- Resample ohne explizite label/closed/origin/offset; Resample in UTC ohne danach Meta/TZ klarzustellen.
- requested_end als date-only ohne definierte Interpretation.
- Timestamps aus Datenquelle als „Market-TZ“ behandeln.


Anhang: Funktionssignaturen (Kurz)
----------------------------------

- time.parse_eodhd_timestamp(raw, gmtoffset=None) -> pd.Timestamp (UTC)
- time.to_market(ts_utc, market_tz) -> pd.Timestamp
- time.to_display(ts_utc, display_tz="Europe/Berlin") -> pd.Timestamp
- time.resolve_session(SessionSpec, ts, market_tz) -> (session_start, session_end)
- time.calculate_validity(signal_ts, bar_spec, session_spec, policy, validity_minutes=60, valid_from_policy="signal_ts") -> (valid_from, valid_to)
- time.bar_timestamp_semantics(bar_ts, bar_spec) -> bar_ts (bar-close)
- time.handle_dst(ts, tz, how="raise") -> pd.Timestamp
