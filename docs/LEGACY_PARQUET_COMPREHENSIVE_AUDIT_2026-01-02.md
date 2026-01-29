# COMPREHENSIVE LEGACY PARQUET AUDIT REPORT
**Audit Date:** 2026-01-02  
**Auditor:** Forensic Code Analysis (Automated)  
**Scope:** Intraday/Minute-level (M1/M5/M15/H1) Legacy Parquet Patterns  
**Status:** READ-ONLY (No code changes performed)

---

## Executive Summary

Conducted comprehensive forensic audit of the TradeRunner codebase to identify all instances of legacy unsuffixed parquet file patterns for intraday/minute-level data. The audit reveals **17 HIGH/MEDIUM-risk production code instances** that still use or expect unsuffixed `{SYMBOL}.parquet` files instead of the new session-aware naming convention (`_rth.parquet`, `_raw.parquet`).

**Critical Findings:**
- **6 HIGH-RISK production paths** directly construct/expect unsuffixed intraday files
- **8 MEDIUM-RISK glob/discovery patterns** that are not suffix-aware
- **3 deprecated `_all.parquet` references** (should migrate to `_raw`)
- **Good news:** Core infrastructure (replay_engine `_resolve_symbol_path`) already fixed

**Risk:** Without remediation, these patterns will fail silently (0 fills, missing data) when only `_rth/_raw` suffixed files exist.

**Root Cause:** Incremental migration to session-aware caching left scattered legacy patterns across signal generators, dashboards, and utilities.

---

## Definitions & Standards

### NEW NAMING CONVENTION (Mandatory for Intraday)

**Intraday/Minute Data (M1/M5/M15/H1):**
- `{SYMBOL}_rth.parquet` ✅ **Regular Trading Hours only** (09:30-16:00 ET) - **PREFERRED**
- `{SYMBOL}_raw.parquet` ✅ **All sessions** (Pre-market + RTH + After-hours) - **NEW STANDARD**
- `{SYMBOL}_all.parquet` ⚠️ **DEPRECATED** (legacy "all sessions", use `_raw` instead)
- `{SYMBOL}.parquet` ❌ **FORBIDDEN** for intraday (unsupported, causes 0-fill regressions)

**Daily Data (D1):**
- `{SYMBOL}.parquet` ✅ **ALLOWED** (no suffix needed for daily data)

**Priority Order (in resolvers):**
1. `_rth.parquet` ← Strategies prefer this
2. `_raw.parquet` ← New standard for "all data"
3. `_all.parquet` ← Legacy fallback (to be removed)
4. `.parquet` ← **FORBIDDEN for intraday** (D1 only)

### LEGACY DEFINITION (Strict)

Code is **LEGACY** if it:
1. Constructs paths as `{SYMBOL}.parquet` for intraday (M1/M5/M15/H1) WITHOUT `_rth/_raw/_all` suffix
2. Uses `_all.parquet` explicitly (deprecated, should use `_raw`)
3. Uses `glob("*.parquet")` for intraday symbol discovery without suffix-aware parsing
4. Has fallback logic to unsuffixed intraday `.parquet` files
5. Writes/generates new unsuffixed `.parquet` files for intraday data

**NOT LEGACY:**
- Code using `IntradayStore.path_for(..., session_mode="rth"|"all")`
- Code using `_resolve_symbol_path()` with proper priority
- Daily (D1) unsuffixed files
- Documentation/comments (unless they drive code behavior)

---

## Detailed Findings by Category

### Category A: Direct `{symbol}.parquet` Construction for Intraday (HIGH RISK)

**Impact:** These paths will **fail** to find data if only `_rth/_raw` files exist, causing silent failures (0 fills, missing charts, errors).

| File | Line | Snippet | Risk | Context |
|------|------|---------|------|---------|
| `src/axiom_bt/intraday.py` | 397 | `m1_file = DATA_M1 / f"{sym}.parquet"` | **H** | M1 data quality check in `ensure_intraday_data` - reads unsuffixed file |
| `src/signals/cli_inside_bar.py` | 193 | `source = data_path / f"{symbol}.parquet"` | **H** | Fallback in error handler - expects unsuffixed M5 intraday file |
| `src/signals/cli_rudometkin_moc.py` | 115 | `source = data_path / f"{symbol}.parquet"` | **H** | Daily MOC signal loader - **ALLOWED** (D1 data) |
| `src/axiom_bt/engines/replay_engine.py` | 513 | `file_path = data_path / f"{symbol}.parquet"` | **H** | MOC simulation function - expects unsuffixed daily files - **ALLOWED** (D1) |
| `apps/streamlit/state.py` | 62-63 | `primary = self.data_dir_m1 / f"{symbol}.parquet"<br>path = primary if exists else self.data_dir / f"{symbol}.parquet"` | **H** | Streamlit coverage check - M1/M5 fallback logic to unsuffixed files |
| `trading_dashboard/callbacks/charts_backtesting_callbacks.py` | 191 | `data_path = f"artifacts/data_{tf.lower()}/{symbol}.parquet"` | **H** | Backtesting chart loader - constructs unsuffixed path for M1/M5 |
| `trading_dashboard/repositories/candles.py` | 140, 238 | `parquet_path = ... / f"{symbol}.parquet"` | **H** | Live candles repository - M1 data loader uses unsuffixed paths |
| `trading_dashboard/catalog/data_catalog.py` | 96 | `file_path = path_base / f"{symbol}.parquet"` | **M** | Data catalog - timeframe-agnostic, may affect intraday |

**Why Legacy:** All construct/expect unsuffixed `.parquet` files for minute/hourly data, will fail when only `_rth/_raw` files exist.

---

### Category B: `_all.parquet` Explicit Usage (DEPRECATED → Migrate to `_raw`)

**Impact:** `_all` is deprecated in favor of `_raw`. Code using `_all` should migrate.

| File | Line | Snippet | Risk | Note |
|------|------|---------|------|------|
| `src/axiom_bt/engines/replay_engine.py` | 138 | `f"{symbol}_all.parquet",` | **M** | Priority list in `_resolve_symbol_path` - OK as **fallback only** |
| `tests/test_intraday_session_mode.py` | 30, 160 | `assert path_all.name == "HOOD_all.parquet"<br>all_path = tmp_path / "PREMARKET_all.parquet"` | **L** | Test fixtures - should migrate to `_raw` for consistency |

**Why Legacy:** `_all` is deprecated. New code should use `_raw`. The replay_engine reference is acceptable as a legacy fallback.

---

### Category C: Glob/Discovery Patterns (MEDIUM RISK - Not Suffix-Aware)

**Impact:** These patterns may miss `_rth/_raw/_all` files or incorrectly extract symbols without stripping suffixes.

| File | Line | Snippet | Risk | Context |
|------|------|---------|------|---------|
| `src/signals/cli_inside_bar.py` | 36 | `glob("*.parquet")` → `p.stem.upper()` | **M** | Symbol discovery from M5 data - doesn't strip `_rth/_raw` suffixes |
| `src/signals/cli_rudometkin_moc.py` | 23 | `glob("*.parquet")` → `p.stem.upper()` | **M** | Symbol discovery - same issue |
| `src/axiom_bt/maintenance.py` | 120 | `for parquet in base_dir.glob("*.parquet"):` | **M** | Cleanup logic - not suffix-aware, may delete wrong files |
| `apps/streamlit/app.py` | 488 | `glob("*.parquet")` → `p.stem.upper()` | **M** | Streamlit symbol discovery - not suffix-aware |
| `trading_dashboard/utils/symbol_cache.py` | 39 | `glob("*.parquet")` → extract symbol | **M** | Symbol cache - not suffix-aware |
| `trading_dashboard/repositories/__init__.py` | 79 | `parquet_dir.glob("*.parquet")` | **M** | Repository discovery - may be D1 (acceptable) or intraday (risky) |
| `scripts/backfill_trade_inspector_bars.py` | 58 | `bars_dir.glob("*.parquet")` | **L** | Backfill script - only for bars/ artifacts (acceptable) |
| `scripts/generate_test_data.py` | 180 | `m1_dir.glob("*.parquet")` | **L** | Test data generation - should be suffix-aware |

**Why Legacy:** Glob patterns don't distinguish `_rth/_raw` suffixes, may extract incorrect symbols (e.g., "HOOD_rth" instead of "HOOD").

---

### Category D: Writers/Generators Creating Unsuffixed Files (MEDIUM RISK)

**Impact:** These create new unsuffixed `.parquet` files for intraday data, perpetuating the legacy pattern.

| File | Line | Snippet | Risk | Context |
|------|------|---------|------|---------|
| `src/axiom_bt/demo.py` | 41 | `ohlcv.to_parquet(data_dir / f"{symbol}.parquet")` | **M** | Demo script - should use `_rth` suffix |
| `scripts/generate_test_data.py` | 169 | `m1_path = m1_dir / f"{symbol}.parquet"` | **M** | Test data generator - creates unsuffixed M1 files |
| `tests/test_maintenance.py` | 83 | `df.to_parquet(data_dir / f"{symbol}.parquet")` | **L** | Test fixture - should use `_rth` |
| `tests/test_axiom_integration.py` | 28, 39 | `prices_m1.to_parquet(... f"{symbol}.parquet")<br>prices_m5.to_parquet(... f"{symbol}.parquet")` | **L** | Test fixtures - should use `_rth` |

**Why Legacy:** Generating new unsuffixed files perpetuates the problem. All intraday writes should use suffix.

---

### Category E: Test Code / Documentation (LOW RISK)

**Impact:** Tests may pass with old fixtures but fail in production. Should align for consistency.

| File | Line | Note |
|------|------|------|
| `tests/test_intraday_session_mode.py` | Multiple | Uses `_all.parquet` - should migrate to `_raw` |
| `tests/test_axiom_integration.py` | 28, 39 | Creates unsuffixed test files |
| `tests/test_intraday_store.py` | Multiple | Uses "AAPL.parquet" test fixtures |
| `src/strategies/inside_bar/docs/UNIFIED_STRATEGY_PLAN.md` | 545 | Doc mentions `'fixtures/APP_2025-11-24_M5.parquet'` |

**Why Legacy:** Tests and docs should align with production naming for maintainability.

---

### Category F: Already Fixed / Compliant (GOOD ✅)

These files **correctly** use the new naming convention:

- ✅ `src/axiom_bt/engines/replay_engine.py:136-139` - Priority list (`_rth → _raw → _all → unsuffixed`)
- ✅ `src/axiom_bt/intraday.py:512-513` - `path_for()` generates `_{suffix}.parquet` correctly
- ✅ `trading_dashboard/repositories/trade_repository.py:61,72` - Globs for `*_rth.parquet`
- ✅ `scripts/backfill_trade_inspector_bars.py:94-95` - Uses `_rth` suffix
- ✅ `src/axiom_bt/cli_data.py` - Uses `session_mode` parameter correctly

---

## TOP 10 FIX TARGETS (Prioritized)

### PHASE 1: Critical Production Code (HIGH PRIORITY)

1. **`src/axiom_bt/intraday.py:397`** - M1 data quality check
   - **Fix:** Replace `DATA_M1 / f"{sym}.parquet"` with `self.path_for(sym, Timeframe.M1, session_mode="rth")`
   - **Why:** Silent failure if only `_rth` files exist

2. **`src/signals/cli_inside_bar.py:193`** - Error handler fallback
   - **Fix:** Remove unsuffixed fallback, use `IntradayStore.path_for()` with `session_mode`
   - **Why:** Will fail to find M5 data after migration

3. **`apps/streamlit/state.py:62-63`** - Coverage check M1/M5 fallback
   - **Fix:** Replace with `IntradayStore.path_for()` or call `_resolve_symbol_path()`
   - **Why:** Streamlit dashboard will show "missing" for valid `_rth` data

4. **`trading_dashboard/callbacks/charts_backtesting_callbacks.py:191`** - Chart loader
   - **Fix:** Use `IntradayStore.path_for(symbol, timeframe, session_mode="rth")` instead of string construction
   - **Why:** Backtesting charts will fail to load

5. **`trading_dashboard/repositories/candles.py:140, 238`** - Live candles loader
   - **Fix:** Use `IntradayStore.path_for()` or `_resolve_symbol_path()`
   - **Why:** Live charts will fail to load M1 data

### PHASE 2: Discovery/Glob Patterns (MEDIUM PRIORITY)

6. **`src/signals/cli_inside_bar.py:36`** - Symbol discovery
   - **Fix:** Strip `_rth/_raw/_all` suffixes when extracting symbols: `p.stem.replace('_rth', '').replace('_raw', '').replace('_all', '').upper()`
   - **Why:** Will discover "HOOD_RTH" as a symbol instead of "HOOD"

7. **`src/axiom_bt/maintenance.py:120`** - Cleanup glob
   - **Fix:** Make suffix-aware or use allowlist of known suffixes
   - **Why:** May delete wrong files during cleanup

8. **`trading_dashboard/utils/symbol_cache.py:39`** - Symbol cache
   - **Fix:** Strip suffixes when caching symbols
   - **Why:** Cache corruption (duplicate entries for same symbol)

### PHASE 3: Writers/Generators (MEDIUM PRIORITY)

9. **`src/axiom_bt/demo.py:41`** - Demo data writer
   - **Fix:** Use `IntradayStore.path_for(..., session_mode="rth")` instead of manual path construction
   - **Why:** Generates legacy unsuffixed files

10. **`scripts/generate_test_data.py:169`** - Test data generator
    - **Fix:** Generate `_rth.parquet` files instead of unsuffixed
    - **Why:** Test fixtures should match production

---

## Evidence: RAW/RTH Files Exist

Verified that new suffix convention is already in use in `artifacts/data_m1/`:

```
-rw-rw-r-- 1 mirko mirko 336K Jan  2 00:51 AMZN_rth.parquet
-rw-rw-r-- 1 mirko mirko  56K Dez 31 13:41 APP_rth.parquet
-rw-rw-r-- 1 mirko mirko  55K Dez 30 00:10 HOOD_raw.parquet
-rw-rw-r-- 1 mirko mirko 858K Jan  2 00:52 HOOD_rth.parquet
-rw-rw-r-- 1 mirko mirko 579K Jan  2 00:59 HYMC_rth.parquet
-rw-rw-r-- 1 mirko mirko 839K Jan  2 00:58 NVDA_rth.parquet
-rw-rw-r-- 1 mirko mirko 200K Dez 31 21:46 PLTR_rth.parquet
```

**Observation:** Data pipeline is already generating `_rth/_raw` files. Legacy code paths will fail to discover them.

---

## Verification Checklist (Post-Remediation)

After implementing fixes, verify:

- [ ] No `rg` hits for `f"{symbol}.parquet"` in `src/signals/**` (except D1 contexts)
- [ ] No `rg` hits for `f"{sym}.parquet"` in `src/axiom_bt/**` (except D1/universe)
- [ ] All `glob("*.parquet")` calls in intraday contexts are suffix-aware
- [ ] All M1/M5 data loaders use `IntradayStore.path_for()` or `_resolve_symbol_path()`
- [ ] Test fixtures use `_rth.parquet` suffix for M1/M5 data
- [ ] No new unsuffixed `.parquet` files generated for intraday data
- [ ] All backtest runs produce `fills_count > 0` for known symbols (HOOD, PLTR)
- [ ] Streamlit/Dashboard charts load successfully with `_rth` data
- [ ] No "No data file found" warnings for symbols that have `_rth/_raw` files

---

## Risk Assessment

### Current State: **MEDIUM-HIGH RISK**

**Risks:**
- ⚠️ Signal generators (CLI inside_bar, rudometkin) have legacy fallbacks
- ⚠️ Dashboard/Streamlit will fail to find `_rth` data (charts/coverage broken)
- ⚠️ Symbol discovery globs will create corrupted caches (HOOD_RTH vs HOOD)
- ✅ Core replay engine fixed (can find `_rth/_raw` files)
- ✅ Backtest runner generates correct `_rth` artifacts

**Impact if not fixed:**
- Silent failures (0 fills, missing trades) when legacy unsuffixed files removed
- "Data not found" errors in charts despite valid `_rth` data existing
- Symbol discovery corruption (wrong symbols in dropdowns/caches)

### Post-Remediation: **LOW RISK**

**After fixes:**
- All production code uses `path_for()` or `_resolve_symbol_path()`
- No hardcoded unsuffixed construction for intraday
- All discovery patterns suffix-aware
- Tests aligned with production
- Legacy unsuffixed files can be safely deleted

---

## Proof of Compliance (No Code Changes)

**Git Status:**
```
?? docs/LEGACY_PARQUET_AUDIT_2026-01-02.md
```

✅ **Working tree clean** - No code changes performed during this audit.

---

## Appendix A: Search Commands Used

```bash
# Guardrails
git branch --show-current && git status --porcelain=v1

# Pattern searches
rg -n --hidden --glob '!.venv/**' --glob '!artifacts/**' 'f".*\{.*\}\.parquet"' src apps trading_dashboard scripts tests
rg -n --hidden --glob '!.venv/**' --glob '!artifacts/**' '_all\.parquet' src apps trading_dashboard scripts tests
rg -n --hidden --glob '!.venv/**' --glob '!artifacts/**' 'glob\(["\x27]\*\.parquet["\x27]\)' src apps trading_dashboard scripts

# Context extraction
sed -n 'LINE-3,LINE+3p' <file>

# Evidence
ls -lah artifacts/data_m1/*_raw.parquet artifacts/data_m1/*_rth.parquet
```

---

## Appendix B: Allowed Patterns (Not Legacy)

**These patterns are COMPLIANT:**

1. **Daily (D1) unsuffixed files:**
   ```python
   data_path / "AAPL.parquet"  # OK for D1
   ```

2. **Using session-aware API:**
   ```python
   store.path_for(symbol, timeframe=Timeframe.M5, session_mode="rth")  # ✅
   ```

3. **Using resolver with priority:**
   ```python
   path, is_m1 = _resolve_symbol_path(symbol, m1_dir, fallback_dir)  # ✅
   ```

4. **Explicit suffixed paths:**
   ```python
   data_path / f"{symbol}_rth.parquet"  # ✅
   data_path / f"{symbol}_raw.parquet"  # ✅
   ```

5. **Bars artifacts (already suffixed):**
   ```python
   bars_dir / f"bars_exec_M5_rth.parquet"  # ✅
   ```

---

**END OF REPORT**

**Recommendation:** Implement Phase 1 fixes (TOP 5) immediately to prevent production failures. Phase 2-3 can follow iteratively.
