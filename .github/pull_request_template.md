<!--
PR TEMPLATE — Traderunner / Marketdata-Stream / Automatictrader-API
SSOT: AGENTS.md + AI_CONTRIBUTION_GUIDE.md + ENGINEERING_MANIFEST.md
Delete sections that are not applicable, but keep the checklists.
-->

# PR: <Kurz-Titel, präzise>

## 0) SSOT / Kontext
- Repo(s): ☐ traderunner ☐ marketdata-stream ☐ automatictrader-api
- Branch: `<branch>`
- Commit (HEAD): `<sha>`
- Related Issue / Incident: `<link|id>`
- Risk Level: ☐ Low ☐ Medium ☐ High

---

## 1) Problem
**1–2 Sätze**: Was ist kaputt / was soll verbessert werden?

### Expected vs Actual
- Expected: …
- Actual: …

---

## 2) Evidence (Beweise)
> Keine “Vermutungen”. Bitte konkrete Pfade / Snippets / Screenshots.

### Logs / Artefacts / Screenshots
- Screenshot(s): `<link or description>`
- Log Snippet(s): `<path + 3–10 lines>`
- Error ID(s): `<error_id>` (falls vorhanden)

### Backtest Runs (falls relevant)
- run_dir: `artifacts/backtests/<run_dir>/`
- run_meta.json: ☐ vorhanden
- run_result.json: ☐ vorhanden
- run_manifest.json: ☐ vorhanden
- error_stacktrace.txt (nur ERROR): ☐ vorhanden

---

## 3) Root Cause
**Kurz und technisch**: Warum ist es passiert?
- File/Function: `<path>#Lx-Ly`
- Mechanismus: …

---

## 4) Lösung (Minimal Diff)
**Was wurde geändert?** (bullet points, keine Romane)
- …
- …

### Affected Files / Modules
- …
- …

---

## 5) Guardrails & Invariants (MUST CHECK)
> Diese Liste ist verpflichtend. Wenn etwas nicht zutrifft: erklären + Fix anpassen.

### Core Invariants
- [ ] Tests-first eingehalten (RED → GREEN)
- [ ] Minimal diff (keine Drive-by Refactors/Formatierungen)
- [ ] Layering eingehalten (Business logic nicht in UI callbacks)
- [ ] Keine Data-Source-Mischung (Backtest Parquet/EODHD vs Live/Pre-Paper SQLite)
- [ ] Market TZ bleibt `America/New_York` (immutable)
- [ ] Strategy Lifecycle / Versioning Regeln eingehalten (Promotion/Atom)
- [ ] SSOT respektiert (keine doppelten Registries/Listen/Configs)

### UI Contract (falls UI betroffen)
- [ ] `run_dir` ist **einziger** Lookup-Key (job_id nie für FS lookup)
- [ ] `bt-active-run` Store wird nur beim Start gesetzt; Polling ist read-only
- [ ] Kein “silent waiting”: nach max. N Polls Diagnose/Fehler sichtbar
- [ ] UI Status kommt **nur** aus `run_result.json` (nicht aus Logs)
- [ ] Logs/Steps sind run-scoped (nur aus `run_dir`, keine globalen “current_*” Quellen)
- [ ] Inputs werden nicht durch Polling/Refresh zurückgesetzt

### Backtest Pipeline Contract (falls Backtesting betroffen)
- [ ] Artifacts always created: `run_meta` am Start; `run_result` + `run_manifest` am Ende (immer)
- [ ] Status Model nur: `SUCCESS | FAILED_PRECONDITION(reason) | ERROR(error_id)`
- [ ] Coverage Gate + SLA Gate sind hard gates (kein Weiterlaufen nach Fail)
- [ ] Keine generische “Pipeline Exception” als primärer Outcome

### Golden / Promotion Gate (falls Golden betroffen)
- [ ] DEV/Lab/INT: Skips erlaubt (wenn Daten fehlen)
- [ ] Promotion: `REQUIRE_GOLDEN_DATA=1` → Skips werden FAIL (“promotion blocked”)

---

## 6) Tests (RED → GREEN Nachweis)
### New/Updated Tests
- Test(s) hinzugefügt/angepasst:
  - `tests/test_<name>.py::test_<case>` (RED → GREEN)
  - …

### Test Commands Run
- [ ] Focused tests:
  - `<command>`
- [ ] Core suite:
  - `PYTHONPATH=src:. pytest -q` (oder repo-spezifisch: …)

### Result Summary
- Passed: `<n>`
- Failed: `<n>`
- Skipped: `<n>` (warum?)
- Runtime: `<time>`

---

## 7) Manual Verification (INT / Local)
> Konkrete Steps, die jemand anders in 2–5 Minuten nachmachen kann.

### Local
1) …
2) …
3) …

### INT (falls deployed)
- URL/Service: `<url / systemd unit>`
- Verify:
  - [ ] Service startet sauber (systemd status)
  - [ ] Keine Errors in letzten 100 log lines
  - [ ] UI Verhalten korrekt (Screenshots/Evidence)

---

## 8) Rollback Plan
Wenn das schiefgeht: wie zurück?
- Revert Commit(s): `<sha>`
- Service restart / config revert: …

---

## 9) Notes / Follow-ups (optional)
- Tech debt bewusst akzeptiert: …
- Phase 6 Aufgaben: …
