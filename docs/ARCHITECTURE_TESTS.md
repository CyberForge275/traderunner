# Architekturtests (Architecture Tests)

Dieses Dokument beschreibt die **Architekturtests** für das Traderunner-Ökosystem
(`traderunner`, `automatictrader-api`, `marketdata-stream`).

Ziel der Architekturtests:

- **Qualität vor Quantität**:
  Lieber wenige, gezielte Guardrails als viele nutzlose Tests.
- Schutz der wichtigsten **Invarianten** der Codebasis.
- Unterstützung der Regeln aus `AI_CONTRIBUTION_GUIDE.md`.
- Früher Alarm, wenn KI (oder Mensch) unbewusst Architekturprinzipien verletzt.

Architekturtests sind **keine** klassische Unit-Tests, sondern prüfen
übergreifende Eigenschaften der Struktur (Layering, Konsistenz, Pfade, etc.).


## 1. Ort & Ausführung

Die Architekturtests liegen im Projekt unter:

- `tests/architecture/`

Beispiele:

- `tests/architecture/test_timeframe_coverage.py`
- `tests/architecture/test_strategy_catalog_consistency.py`
- `tests/architecture/test_no_hardcoded_paths.py`

Ausführung (Beispiel):

```bash
cd traderunner
python -m pytest tests/architecture -q
