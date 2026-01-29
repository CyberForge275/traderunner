# CHANGELOG - Session Mode Cache Suffix (Mini-Step)

**Feature**: Configurable RTH vs ALL-hours session modes with separate cache files  
**Branch**: `feature/session-mode-cache-suffix`  
**Baseline SHA**: `85de37ead1229ca6e84dc98695e88c5d789158c6`  
**Date**: 2025-12-28

---

## FILES TOUCHED (Minimal Scope)

1. **src/axiom_bt/intraday.py** (Lines: 194-215, 262, 317, 364, 371-376, 427-459, 465-475)
   - `IntradaySpec`: Add `session_mode` field
   - `IntradayStore.path_for()`: Add session suffix to filenames
   - `IntradayStore.ensure()`: Use `spec.session_mode` for filtering
   - `IntradayStore.load()`: Add RTH validation gate

   - Extract `session_mode` from `strategy_params`
   - Pass to `IntradaySpec` and `store.load()`

3. **tests/test_intraday_session_mode.py** (NEW)
   - Cache key separation test
   - RTH validation gate test

---

## BEHAVIOR CHANGES

### BEFORE:
- **Cache collision**: Only one cache file per symbol (`HOOD.parquet`)
- **RTH hardcoded**: Always `filter_rth=True` in ensure()
- **No validation**: Files could be mislabel as RTH-only but contain Pre/After data
- **No configurability**: Cannot run ALL-hours backtests

### AFTER:
- **Separate caches**: `HOOD_rth.parquet` vs `HOOD_all.parquet` (no collision)
- **Configurable filter**: `session_mode="rth"` → RTH-only, `session_mode="all"` → Pre+RTH+After
- **Fail-fast validation**: `*_rth.parquet` files MUST pass RTH gate on load (ValueError if non-RTH bars found)
- **Backward compatible**: Default `session_mode="rth"` preserves existing behavior
- **Config path**: Set `strategy_params["session_mode"]` in YAML/call to enable ALL-hours

---

## EVIDENCE / BELEGE

### 1. IntradaySpec Location
**File**: `src/axiom_bt/intraday.py`  
**Line**: 194  
```python
@dataclass(frozen=True)
class IntradaySpec:
```

### 2. path_for() Location
**File**: `src/axiom_bt/intraday.py`  
**Line**: 465  
```python
def path_for(self, symbol: str, *, timeframe: Timeframe) -> Path:
```

### 3. ensure() filter_rth Hardcoding
**File**: `src/axiom_bt/intraday.py`  
**Lines**: 317, 364  
```python
filter_rth=True,  # ← HARDCODED, needs dynamic
```

### 4. resample_m1() Output Naming
**File**: `src/axiom_bt/data/eodhd_fetch.py`  
**Lines**: 431-432  
```python
symbol = m1_parquet.stem  # ← KEEPS INPUT STEM
path = out_dir / f"{symbol}.parquet"
```
**[BELEG]**: resample_m1 ALREADY preserves stem → NO CHANGE NEEDED for resample logic

### 5. IntradaySpec Call Site
**Lines**: 275-281  
```python
spec = IntradaySpec(
    symbols=[symbol],
    start=start_ts.date().isoformat(),
    end=end_ts.date().isoformat(),
    timeframe=tf_enum,
    tz=market_tz,
    # ← INSERT session_mode here
)
```

---

## ROLLBACK PLAN

### Option A: Revert on main (preferred if merged)
```bash
# Find commit SHAs of feature
git log --oneline --grep="session.*mode" -n 5

# Revert in reverse order
git revert <commit3_sha> <commit2_sha> <commit1_sha>
git push origin main
```

### Option B: Delete branch (if not merged yet)
```bash
git checkout main
git branch -D feature/session-mode-cache-suffix
# If pushed:
git push origin --delete feature/session-mode-cache-suffix
```

### Option C: Hard reset (local only, NOT pushed)
```bash
git reset --hard $(cat /tmp/before_sha.txt)
# OR
git reset --hard 85de37ead1229ca6e84dc98695e88c5d789158c6
```

---

## VERIFICATION CHECKLIST

- [ ] Branch created: `feature/session-mode-cache-suffix`
- [ ] Baseline SHA saved: `85de37ead1229ca6e84dc98695e88c5d789158c6`
- [ ] IntradaySpec has `session_mode` field
- [ ] path_for() returns `{symbol}_rth.parquet` or `{symbol}_all.parquet`
- [ ] ensure() uses `spec.session_mode` for filter_rth
- [ ] load() validates RTH for `*_rth.parquet` files
- [ ] Tests added: cache separation + RTH validation
- [ ] Smoke test: RTH mode produces `*_rth.parquet` with no Pre/After bars
- [ ] Smoke test: ALL mode produces `*_all.parquet` with Pre+After bars
- [ ] Both cache files can coexist without collision

---

**Generated**: 2025-12-28T11:43:44+01:00  
**Status**: RECON COMPLETE → READY FOR IMPLEMENTATION
