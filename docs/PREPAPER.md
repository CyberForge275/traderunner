# PrePaper Lab MVP - Quick Start

**Date**: 2026-01-07  
**Status**: 🚧 IN DEVELOPMENT (MS1-MS3 ✅ COMPLETE)

---

## What is PrePaper?

PrePaper is an isolated lab environment for testing strategies on **replay data** or **live WebSocket feeds** before paper trading. It:

- ✅ Generates deterministic order **plans** (no broker execution)
- ✅ Uses `marketdata-service` interface (transport-agnostic: HTTP/WS/Fake)
- ✅ Writes signals/intents to `signals.db` (via service, never directly)
- ✅ Produces audit-friendly artifacts (`plan.json`, `run_manifest.json`)
- ❌ Does NOT submit orders to brokers
- ❌ Does NOT access `axiom_bt/data` or `signals.db` directly

---

## Installation (Developer Setup)

### Prerequisites
- Python 3.10+
- `traderunner` and `marketdata-monorepo` repos cloned

### Install `marketdata-service` as editable package

```bash
# 1. Install marketdata-service in your traderunner venv
cd ~/data/workspace/droid/traderunner
source .venv/bin/activate

cd ../marketdata-monorepo
pip install -e .

# 2. Verify import works
python -c "import marketdata_service; print(marketdata_service.__file__)"
# Expected: /path/to/marketdata-monorepo/src/marketdata_service/__init__.py
```

### Alternative: Manual PYTHONPATH (for quick testing)

```bash
export PYTHONPATH="/home/mirko/data/workspace/droid/marketdata-monorepo/src:$PYTHONPATH"
```

---

## Quick Test

```bash
cd ~/data/workspace/droid/traderunner

# Run PrePaper port tests
pytest tests/test_prepaper_marketdata_port.py -v
# Expected: 5/5 passed

# Run all PrePaper tests (when MS4 complete)
pytest tests/test_prepaper_* -v
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  PrePaper Runner (traderunner)              │
│  ├─ marketdata_port.py (ONLY data access)  │
│  └─ plan.json, run_manifest.json           │
└──────────────┬──────────────────────────────┘
               │ (MarketDataService interface)
               ▼
┌─────────────────────────────────────────────┐
│  marketdata-monorepo                        │
│  ├─ FakeMarketDataService (MVP/tests)      │
│  ├─ SignalsStore (sqlite, idempotent)      │
│  └─ (Future: HTTP/WS providers)            │
└─────────────────────────────────────────────┘
```

**Key Principle**: PrePaper **NEVER** knows if data comes from HTTP, WebSocket, or Fake—it only uses the `MarketDataService` interface.

---

## Guards & Safety

PrePaper has **architecture guards** that prevent:

- ❌ Direct `sqlite3.connect()` calls → must use `marketdata_service.signals_write/query`
- ❌ Imports from `axiom_bt/data` → must use `marketdata_port.get_replay_bars`
- ❌ Writes outside `artifacts/prepaper/<run_id>/`

**Tests verify these guards**:
- `test_prepaper_never_opens_signals_db()` - monkeypatches `sqlite3.connect` to fail
- `test_prepaper_no_axiom_bt_data_imports()` - scans source for forbidden imports

---

## Usage (MVP - MS4 in progress)

```bash
# Example: Run PrePaper with FakeMarketDataService (for testing)
cd ~/data/workspace/droid/traderunner

python -m pre_paper.runner \
  --backtest-run-id 251215_144939_HOOD_M5_100d \
  --replay-date 2025-12-15 \
  --mode replay

# Outputs:
# artifacts/prepaper/<run_id>/
#   ├── plan.json            (deterministic order plan)
#   ├── run_manifest.json    (with marketdata_data_hash)
#   ├── run_meta.json        (human-readable metadata)
#   └── signals_export.json  (optional: run-scoped signals)
```

---

## Determinism Guarantee (Replay Mode)

**Replay mode** with same inputs produces **same `plan_hash`**:
- Same backtest manifest
- Same replay date range
- Same `run_id` (for tests via `--run-id`)

**Live/WS mode** is marked `mode="live"` in manifest → determinism tests skipped.

---

## Development Status (2026-01-07)

| Phase | Status | Commit SHA | Tests |
|:------|:-------|:-----------|:------|
| MS1: MarketDataService Interface | ✅ DONE | a6f0109 | 7/7 |
| MS2: SignalsStore (idempotent) | ✅ DONE | 833002a | 5/5 |
| MS3: PrePaper Port + Guards | ✅ DONE | 697dc03 | 5/5 |
| MS4: Plan + Manifest + Determinism | 🚧 IN PROGRESS | - | - |
| MS5: WS-only Minute Aggregation | ⏸ PLANNED | - | - |

**Total Tests**: 17/17 marketdata-monorepo + 5/5 traderunner = **22/22 passing**

---

## Troubleshooting

### `ImportError: No module named 'marketdata_service'`

**Solution**: Install marketdata-monorepo as editable package (see Installation above).

### `FORBIDDEN: PrePaper tried to open SQLite DB directly!`

**Cause**: Code is calling `sqlite3.connect()` instead of using `marketdata_port.write_signals/query_signals`.

**Solution**: Use the port methods only.

### Tests fail with path errors

**Solution**: Ensure you're running tests from `traderunner/` root:
```bash
cd ~/data/workspace/droid/traderunner
pytest tests/test_prepaper_*
```

---

## Next Steps (Post-MS4)

1. **MS5**: WS-only tick aggregation (live mode)
2. **Dashboard Integration**: PrePaper results visualization
3. **Promotion Pipeline**: Backtest → PrePaper → Paper → Live
4. **LabContext SSOT**: Explicit lab identity enforcement

---

## See Also

- `docs/LAB_ATOMICITY_AUDIT.md` - Lab isolation architecture
- `docs/FACTORY_LABS_AND_STRATEGY_LIFECYCLE.md` - Strategy promotion pipeline
- `marketdata-monorepo/README.md` - MarketData service SSOT

---

**Questions?** Check scoreboard: `brain/*/prepaper_scoreboard.md`
