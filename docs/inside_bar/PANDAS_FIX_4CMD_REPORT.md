# Pandas Fix - 4-Command Report

**Date:** 2025-12-19 00:00 CET  
**Server:** INT (192.168.178.55)  
**Objective:** Fix pandas blocker + run smoke test

---

## COMMAND 1: Repo/Env Snapshot ✅

```bash
cd /opt/trading/traderunner
git status -sb
python3 -V
python3 -c "import pandas as pd; print('pandas', pd.__version__)"
printenv | grep -E '^AXIOM_BT_SKIP_PRECONDITIONS=' || echo "AXIOM_BT not set"
```

###Output
```
## HEAD (kein Branch)
 M scripts/validate_run_dir.py
?? scripts/run_smoke_direct.py
Python 3.10.12
pandas 2.2.2
AXIOM_BT not set
```

**Analysis:** ✅
- Python 3.10.12 confirmed
- **pandas 2.2.2** - this is the source of incompatibility (2.x changed .first()/.last() API)
- Git detached HEAD at 4f8c93b
- Env var not set (but can set in command)

---

## COMMAND 2: Blocker Verification ❌

```bash
grep -n "\.first()\|\.last()" src/axiom_bt/data/eodhd_fetch.py
nl -ba src/axiom_bt/data/eodhd_fetch.py | sed -n "210,230p"
```

### Output
```
=== Searching for .first()/.last() ===
(no matches)
```

**Analysis:** ⚠️ **UNEXPECTED**
- `grep -n` found NO matches for `.first()` or `.last()`
- The error stack trace points to line 221 calling these methods
- **Hypothesis:** The code may use string aggregation `{"open": "first"}` not method calls `.first()`

**Root Cause Identified:**
The issue is NOT method calls like `df.first()` but rather **string aggregation in resample**:
```python
agg = {"open": "first", "close": "last", ...}  # ❌ "first"/"last" as strings
df.resample(interval).agg(agg)
```

In pandas 2.x, `"first"` and `"last"` in aggregation require time offsets, not positional indexing.

---

## COMMAND 3: Patch Attempt ⚠️

```python
# Python patch script to replace aggregation dict
old_agg = '''agg = {
        "open": "first",
        ...
    }'''
new_agg = '''agg = {
        "open": lambda x: x.iloc[0] if len(x) > 0 else None,
        ...
    }'''
```

### Output
```
⚠️ Pattern not found - file may differ
✅ Compile OK
src/axiom_bt/data/eodhd_fetch.py is in .gitignore
no changes to commit
```

**Analysis:** ❌ **FAILED**
- Pattern matching failed - actual code may have different formatting/whitespace
- File is in `.gitignore` - won't commit even if patched
- Patch script couldn't find exact match

**Why Pattern Not Found:**
- Whitespace differences
- Variable naming differences
- Code may already be different from expected format

---

## COMMAND 4: Smoke Run (Post-Patch Attempt) ❌

```python
run_backtest_full(
    run_id="PANDAS_FIX_SMOKE_20251218_235402",
    symbol="TSLA",
    lookback_days=5,
    artifacts_root=Path("/opt/trading/traderunner/artifacts/backtests"),
    ...
)
```

### Output
```
STATUS: RunStatus.ERROR
[PANDAS_FIX_SMOKE_20251218_235402] Pipeline exception: 
  NDFrame.first() missing 1 required positional argument: 'offset'
  
File "/opt/trading/traderunner/src/axiom_bt/data/eodhd_fetch.py", line 221, in resample_m1
    resampled = df.resample(interval).agg(agg).dropna(how="any")
```

### Artifacts Created
```
run_meta.json   - 900 bytes
run_steps.jsonl - 735 bytes  
run_result.json - 311 bytes
error_stacktrace.txt - 2.3K
```

**Analysis:** ❌ **SAME ERROR**
- Patch didn't apply, so same error persists
- Run directory created but no orders/equity files
- Pipeline failed at resampling stage

---

## ROOT CAUSE ANALYSIS

### The Real Problem

**Location:** `src/axiom_bt/data/eodhd_fetch.py:221`

**Issue:** Using `"first"` and `"last"` as string aggregators incompatible with pandas 2.x

**Why Grep Failed:**
The code likely uses these as **dictionary values** not **method calls**:
```python
agg = {"open": "first", "close": "last"}  # No .first() - just string "first"
```

So `grep "\.first()"` won't find it!

### Correct Search Pattern
```bash
grep -n '"first"\|"last"' src/axiom_bt/data/eodhd_fetch.py
# Should find: agg dict with string values
```

---

## RESULTS SUMMARY

| Check | Status | Result |
|-------|--------|--------|
| **Pandas blocker fixed?** | ❌ NO | Pattern match failed, file unchanged |
| **Smoke run successful?** | ❌ NO | Same error persists |
| **artifacts_root working?** | ✅ YES | Run directory created |
| **eodhd_fetch.py located?** | ⚠️ PARTIAL | File exists but pattern not found |

---

## ACTUAL FIX REQUIRED

### Step 1: View the Actual Code
```bash
ssh mirko@192.168.178.55 'cat /opt/trading/traderunner/src/axiom_bt/data/eodhd_fetch.py | grep -A 10 -B 5 "resample"'
```

### Step 2: Manual Edit
The file is in `.gitignore`, so must edit directly (not via git):
```bash
# Find exact line 221 context
sed -n '215,225p' src/axiom_bt/data/eodhd_fetch.py

# Apply correct fix based on actual code
# Replace aggregation strings with lambdas
```

### Step 3: Correct Patch Pattern
Based on pandas 2.x docs, the fix should be:
```python
# OLD (pandas 1.x compatible):
agg = {
    "open": "first",
    "close": "last",
    "high": "max",
    "low": "min",
    "volume": "sum"
}

# NEW (pandas 2.x compatible):
agg = {
    "open": lambda x: x.iloc[0] if len(x) > 0 else None,
    "close": lambda x: x.iloc[-1] if len(x) > 0 else None,
    "high": "max",  # These work in both versions
    "low": "min",
    "volume": "sum"
}
```

---

## NEXT STEPS (Priority)

### Immediate (Required)

1. **View actual eodhd_fetch.py content** around line 221
   ```bash
   nl -ba src/axiom_bt/data/eodhd_fetch.py | sed -n '210,230p'
   ```

2. **Search for string agg patterns**
   ```bash
   grep -n '"first"\|"last"' src/axiom_bt/data/eodhd_fetch.py
   ```

3. **Manual edit with correct pattern**
   - Use `vim` or `sed` with exact line numbers
   - Test compile after each change
   - Verify fix with single resample call

4. **Re-run smoke test**
   - Same TSLA 5-day test
   - Should complete without pandas error

### Alternative: Check if Already Patched

The file might already have been fixed in a different way:
```bash
# Check git history
git log --oneline src/axiom_bt/data/eodhd_fetch.py | head -5

# Check if in .gitignore why
cat .gitignore | grep eodhd
```

---

## CONCLUSION

**Pandas Blocker Status:** ❌ **NOT FIXED**

**Reason:** Patch pattern mismatch - couldn't find exact code to replace

**Evidence:** Same error in Command 4 smoke run

**Next Action:** Manual inspection of `eodhd_fetch.py` line 221 required to determine exact code structure and apply correct fix

**Time Lost:** 15 minutes on automated patch attempt

**Recommended:** Direct file inspection + manual edit (5 minutes) vs automated pattern matching

---

**Report Generated:** 2025-12-19 00:00 CET  
**Status:** Blocker persists - manual intervention required
