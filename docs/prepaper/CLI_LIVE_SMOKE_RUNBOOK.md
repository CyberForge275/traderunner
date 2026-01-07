# PrePaper CLI Live Smoke Test Runbook

**Date**: 2026-01-07  
**Purpose**: Prove marketdata-service live integration + signals.db roundtrip  
**Status**: 🚧 DISCOVERY

---

## 0. AUDIT CLOSURE: All Commit SHAs Verified ✅

### traderunner commits
```bash
837e7fd feat(ms4-3): add signals roundtrip + replay determinism proof
fe68955 feat(ms4-2): add ManifestWriter with hashes + provenance
3974605 feat(ms4-1): add deterministic PlanWriter + tests
7ad1521 docs(prepaper): add installation and usage guide
697dc03 feat(ms3): add PrePaper MarketDataPort adapter + guards
```

### marketdata-monorepo commits
```bash
833002a feat(ms2): add SignalsStore with idempotent writes + stable ordering
a6f0109 feat(ms1): add MarketDataService interface + FakeProvider
```

**Audit Status**: ✅ No pending SHAs

---

## 1. CLI Entry Point Discovery

### Current Implementation (PoC)
```bash
# Entry point found in:
src/pre_paper/pre_paper_runner.py:221

# Current invocation (example only):
if __name__ == "__main__":
    runner = PrePaperRunner(
        backtest_run_id="251215_144939_HOOD_15m_100d",
        artifacts_root=Path("artifacts")
    )
    result = runner.run_strategy_if_sufficient(...)
```

### Direct Python Invocation
```bash
cd ~/data/workspace/droid/traderunner
source .venv/bin/activate

python -m pre_paper.pre_paper_runner
```

**Status**: ⚠️ **NOT MVP-READY**
- Current implementation is PoC only
- No argparse/click CLI
- No config file support
- No --run-id flag

### Recommended: Minimal CLI Wrapper Needed

For live smoke test, we need:
```python
# src/pre_paper/cli.py (NEW)
import argparse
from pathlib import Path
from pre_paper.pre_paper_runner import PrePaperRunner

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest-run-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifacts-root", default="artifacts")
    args = parser.parse_args()
    
    runner = PrePaperRunner(
        backtest_run_id=args.backtest_run_id,
        artifacts_root=Path(args.artifacts_root)
    )
    # TODO: integrate marketdata_port, plan_writer, manifest_writer
    
if __name__ == "__main__":
    main()
```

---

## 2. Provider/Config Discovery

### marketdata-service Provider Status

**Found**: Only `FakeMarketDataService` exists
- File: `src/marketdata_service/fake_provider.py`
- No real provider implemented yet

**Missing for Live Smoke:**
- Real SignalsStore provider
- Config/env switch for provider selection
- Integration with existing `/opt/trading/marketdata-stream/data/signals.db`

### Recommended: Minimal RealSignalsProvider

For live smoke, we need minimal integration:
```python
# marketdata-monorepo/src/marketdata_service/real_provider.py (NEW)
class RealMarketDataService:
    def __init__(self, signals_db_path: str):
        from .signals_store import SignalsStore
        self.signals_store = SignalsStore(Path(signals_db_path))
    
    async def signals_write(self, request):
        return self.signals_store.write_batch(request)
    
    async def signals_query(self, query):
        return self.signals_store.query_run(query)
    
    # TODO: get_bars, ensure_features (can use FakeService for MVP)
```

### Config Pattern
```python
# Environment variable approach
MARKETDATA_PROVIDER = os.getenv("MARKETDATA_PROVIDER", "fake")
SIGNALS_DB_PATH = os.getenv("SIGNALS_DB_PATH", "/opt/trading/marketdata-stream/data/signals.db")

if MARKETDATA_PROVIDER == "real":
    service = RealMarketDataService(signals_db_path=SIGNALS_DB_PATH)
else:
    service = FakeMarketDataService()
```

---

## 3. Gap Analysis: MVP vs Live Smoke

### What We Have ✅
- ✅ Interface contract (MarketDataService)
- ✅ PrePaperMarketDataPort (wrapper)
- ✅ PlanWriter (deterministic)
- ✅ ManifestWriter (hashes)
- ✅ Determinism tests (passing)
- ✅ Architecture guards (passing)

### What's Missing for Live Smoke ⚠️
- ❌ CLI entry with --run-id flag
- ❌ Integration: PrePaperRunner → PlanWriter → ManifestWriter → Port
- ❌ Real signals provider (minimal: SignalsStore wrapper)
- ❌ Config/env for provider selection
- ❌ Run orchestration (bars → signals → plan → manifest → artifacts)

---

## 4. Recommended Path Forward

### Option A: Minimal Integration (1-2 hours)
Create minimal glue code to demonstrate end-to-end flow:

**WP-LIVE-001**: Minimal CLI + Integration
- CREATE `src/pre_paper/cli.py` (argparse wrapper)
- UPDATE `pre_paper_runner.py` to use port + plan_writer + manifest_writer
- CREATE `marketdata_service/real_provider.py` (SignalsStore wrapper only)
- ENV: `MARKETDATA_PROVIDER=real SIGNALS_DB_PATH=.../signals_smoke.db`

**WP-LIVE-002**: Smoke Test Execution
- Copy signals.db to smoke location
- Run CLI with real provider
- Verify artifacts + manifest + db roundtrip
- Document evidence

### Option B: Continue with Fake (Testing Only)
- Use FakeMarketDataService for now
- Focus on BASELINE_FIX (merge blocker)
- Defer real integration until post-merge

---

## 5. Next Decision Point

**RECOMMENDATION**: Option A (Minimal Integration)

**Rationale**:
- Proves end-to-end architecture works
- Validates signals.db integration (critical)
- Small scope (1-2h implementation)
- Provides audit evidence before merge

**User Input Needed**:
1. Approve Option A vs Option B?
2. If Option A: Proceed with WP-LIVE-001 implementation?
3. If Option B: Prioritize BASELINE_FIX instead?

---

## Appendix: Commands for Copy/Paste (Ready to Execute)

### Option A: DEV Smoke Test (Recommended - No sudo)

**1. Setup Smoke DB (HOME path)**
```bash
# Smoke DB under HOME (user-writable, no sudo)
DB_SMOKE_DIR="$HOME/data/marketdata-stream/data/_smoke"
DB_SMOKE="$DB_SMOKE_DIR/signals_smoke.db"

mkdir -p "$DB_SMOKE_DIR"

# Start with empty DB
rm -f "$DB_SMOKE"
touch "$DB_SMOKE"

ls -la "$DB_SMOKE"
```

**2. Set ENV Variables**
```bash
export MARKETDATA_PROVIDER=real
export SIGNALS_DB_PATH="$DB_SMOKE"

echo "MARKETDATA_PROVIDER=$MARKETDATA_PROVIDER"
echo "SIGNALS_DB_PATH=$SIGNALS_DB_PATH"
```

**3. Run CLI with Real Provider**
```bash
cd ~/data/workspace/droid/traderunner
source .venv/bin/activate
cd src

RUN_ID="DEV_LIVE_CLI_001"
BACKTEST_ID="test_backtest_real_provider"  # Replace with actual backtest run ID

python -m pre_paper.cli \
  --backtest-run-id "$BACKTEST_ID" \
  --run-id "$RUN_ID" \
  --artifacts-root "/tmp/prepaper_live_smoke"
```

**Expected Output:**
```
Using RealMarketDataService (signals_db=.../signals_smoke.db)
PrePaper Run: DEV_LIVE_CLI_001
...
Signals written: X, duplicates skipped: 0
✅ PrePaper run complete
```

**4. Verify Artifacts**
```bash
RUN_DIR="/tmp/prepaper_live_smoke/prepaper/$RUN_ID"
ls -la "$RUN_DIR"

# Check manifest
jq . "$RUN_DIR/run_manifest.json" | head -50
```

**5. Verify signals.db Roundtrip**
```bash
# Check signals were written to REAL DB
sqlite3 "$DB_SMOKE" "SELECT lab, run_id, source_tag, COUNT(*) 
FROM signals 
WHERE run_id='$RUN_ID' 
GROUP BY lab, run_id, source_tag;"

# Sample signals (stable ordering)
sqlite3 "$DB_SMOKE" "SELECT ts, symbol, idempotency_key 
FROM signals 
WHERE run_id='$RUN_ID' 
ORDER BY ts, symbol, idempotency_key 
LIMIT 5;"
```

**6. Test Idempotency (Re-run same run_id)**
```bash
# Re-run with same run_id
cd ~/data/workspace/droid/traderunner/src
python -m pre_paper.cli \
  --backtest-run-id "$BACKTEST_ID" \
  --run-id "$RUN_ID" \
  --artifacts-root "/tmp/prepaper_live_smoke"

# Expected: "duplicates skipped: X" (no new writes)

# Verify count unchanged
sqlite3 "$DB_SMOKE" "SELECT COUNT(*) FROM signals WHERE run_id='$RUN_ID';"
```

**7. Cleanup (Optional)**
```bash
rm -rf "/tmp/prepaper_live_smoke"
rm -f "$DB_SMOKE"
```

---

### Option B: INT/PROD Paths (Requires sudo)

For integration/production environments with /opt/trading:

```bash
# System path (requires sudo for setup)
DB_PROD="/opt/trading/marketdata-stream/data/signals.db"
DB_SMOKE_DIR="/opt/trading/marketdata-stream/data/_smoke"
DB_SMOKE="$DB_SMOKE_DIR/signals_smoke.db"

sudo mkdir -p "$DB_SMOKE_DIR"

# Copy from prod OR create empty
if [ -f "$DB_PROD" ]; then
  sudo cp -a "$DB_PROD" "$DB_SMOKE"
else
  sudo touch "$DB_SMOKE"
fi

sudo ls -la "$DB_SMOKE"

# Set ENV (same pattern as Option A)
export MARKETDATA_PROVIDER=real
export SIGNALS_DB_PATH="$DB_SMOKE"

# Run CLI (same as Option A)
```

---

**Status**: Awaiting user decision on Option A vs Option B
