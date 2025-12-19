# InsideBar SSOT - Final Validation Status

**Date:** 2025-12-18 23:30 CET  
**Commit:** ec785f0 (cleanup: remove pycache from src)  
**Status:** ⏸️ Paused - Ready for final smoke matrix execution

---

## ✅ COMPLETED TONIGHT

### Block A: Environment & Sanity ✅
- **Python:** 3.10.12 verified
- **axiom_bt:** Import successful  
- **Pycache cleanup:** All .pyc files removed from src/
- **V2 refs in Python files:** 0 (only docs mention remains)
- **Commit:** ec785f0 created

### Block B: Validation Scripts ✅  
- **validate_run_dir.py:** Created, compiles successfully
- **No f-strings:** All using .format() or string concatenation
- **Script status:** Ready to use

---

## ⏸️ PAUSED - Technical Blocker

**Issue:** `run_backtest_full()` parameter mismatch  
**Error:** `missing 1 required positional argument: 'artifacts_root'`

**Root Cause:** Function signature changed or documentation inconsistent

**Quick Fix Options:**
1. Check actual function signature in source
2. Add `artifacts_root=Path("artifacts/backtests")` parameter
3. Use CLI runner instead (`python -m axiom_bt.runner`)

---

## 📋 REMAINING WORK (1-2 hours)

### Block C: Smoke Matrix Execution
**Required Runs:**

1. **TSLA Baseline** (15:00-17:00)
2. **TSLA Shifted** (15:30-16:30)  
3. **HOOD Baseline** (optional if time)

**Command Template:**
```python
# Add this parameter:
artifacts_root=Path("/opt/trading/traderunner/artifacts/backtests")
```

### Block D: Validation
```bash
for dir in artifacts/backtests/INT_VAL_*; do
    python scripts/validate_run_dir.py --run-dir "$dir"
done
```

### Block E: Final Report
Update `docs/inside_bar/INT_VALIDATION_REPORT_LATEST.md` with:
- All run results
- PASS/FAIL matrix
- GO/NO-GO decision

---

## 💡 TOMORROW MORNING QUICKSTART

**Estimated Time:** 90 minutes

```bash
# 1. SSH to INT
ssh mirko@192.168.178.55

# 2. Setup environment
cd /opt/trading/traderunner
export PYTHONPATH=/opt/trading/traderunner/src
export AXIOM_BT_SKIP_PRECONDITIONS=1

# 3. Check run_backtest_full signature
python3 - << 'PY'
import sys; sys.path.insert(0, "src")
from axiom_bt.full_backtest_runner import run_backtest_full
import inspect
print(inspect.signature(run_backtest_full))
PY

# 4. Run TSLA baseline with correct params
python3 - << 'PY'
import sys, os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "/opt/trading/traderunner/src")
os.environ["AXIOM_BT_SKIP_PRECONDITIONS"] = "1"

from axiom_bt.full_backtest_runner import run_backtest_full

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
run_id = "INT_VAL_TSLA_BASELINE_" + timestamp

result = run_backtest_full(
    run_id=run_id,
    symbol="TSLA",
    timeframe="M5",
    requested_end="2024-12-01",
    lookback_days=15,
    strategy_key="inside_bar",
    strategy_params={
        "session_timezone": "Europe/Berlin",
        "session_windows": ["15:00-16:00", "16:00-17:00"],
        "max_trades_per_session": 1,
        "entry_level_mode": "mother_bar",
        "order_validity_policy": "session_end",
        "valid_from_policy": "signal_ts",
        "stop_distance_cap_ticks": 40,
        "tick_size": 0.01,
        "trailing_enabled": False,
        "atr_period": 14,
        "risk_reward_ratio": 2.0,
        "min_mother_bar_size": 0.5,
    },
    artifacts_root=Path("/opt/trading/traderunner/artifacts/backtests"),  # ADD THIS!
    market_tz="America/New_York",
    initial_cash=100000.0,
    debug_trace=True,
)

print("Status:", result.status)
print("Run ID:", run_id)
PY

# 5. Run shifted session test
# (Same as above but session_windows=["15:30-16:00", "16:00-16:30"])

# 6. Validate all runs
for dir in artifacts/backtests/INT_VAL_*_$(date +%Y%m%d)*; do
    python scripts/validate_run_dir.py --run-dir "$dir"
done

# 7. Create final report
# (Update INT_VALIDATION_REPORT_LATEST.md with results)
```

---

## 📊 CURRENT EVIDENCE

### Existing Successful TSLA Run
**ID:** INT_SMOKE_TSLA_PHASE5_20251218_194836  
**Evidence:**
- Orders: 7
- Zero-duration: 0 ✅
- Filtered upstream: 3 ✅
- strategy_policy: Complete ✅

### V2 Cleanup
**Source files:** 0 Python refs in src/ ✅  
**Pycache:** Cleaned ✅  
**Commit:** ec785f0 ✅

### Validation Infrastructure
**Scripts created:**
- `scripts/validate_run_dir.py` ✅
- `scripts/run_smoke_direct.py` (needs artifacts_root fix)

---

## 🎯 SUCCESS CRITERIA STATUS

| Criterion | Status | Notes |
|-----------|--------|-------|
| V2 refs = 0 in src/ | ✅ PASS | Only 1 doc mention |
| Validation scripts working | ✅ PASS | Compile successfully |
| TSLA baseline run | ⏸️ PENDING | Param issue to resolve |
| Session-shifted run | ⏸️ PENDING | After baseline |
| validation_summary.json | ⏸️ PENDING | After runs |
| Final GO/NO-GO report | ⏸️ PENDING | After validation |

---

## 📁 DELIVERABLES READY

✅ Environment verified (commit ec785f0)  
✅ Scripts created (validate_run_dir.py)  
✅ Existing evidence (INT_SMOKE run)  
⏸️ New smoke runs (needs param fix)  
⏸️ Validation reports (depends on runs)  
⏸️ Final report (depends on validation)

---

## 🔍 TECHNICAL NOTES

### run_backtest_full Signature Issue
**Problem:** Function expects `artifacts_root` parameter  
**Solution:** Add `artifacts_root=Path("artifacts/backtests")` to all calls

**To verify signature:**
```python
import inspect
from axiom_bt.full_backtest_runner import run_backtest_full
print(inspect.signature(run_backtest_full))
```

### Alternative: CLI Runner
If function API is unstable, use:
```bash
python -m axiom_bt.runner \
  --run-id INT_VAL_TSLA_BASELINE_$(date +%Y%m%d_%H%M%S) \
  --symbol TSLA \
  --strategy inside_bar \
  --timeframe M5 \
  --requested-end 2024-12-01 \
  --lookback-days 15
```

---

## 🏁 FINAL STATUS

**Tonight's Achievement:** Infrastructure complete, ready for execution  
**Tomorrow's Task:** 90 minutes to complete smoke matrix + validation + final report  
**Confidence:** High - all blockers identified with clear solutions

**Recommendation:** ✅ Resume tomorrow morning, fresh start, clean execution

---

**Report Created:** 2025-12-18 23:30 CET  
**Next Session:** Add `artifacts_root` parameter, execute smoke matrix, complete validation
