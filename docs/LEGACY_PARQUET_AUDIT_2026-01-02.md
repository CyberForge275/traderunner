# LEGACY PARQUET AUDIT REPORT

## Executive Summary

Conducted forensic audit of codebase to identify legacy code using unsuffixed parquet files (e.g., `SYMBOL.parquet`) instead of new naming conventions (`_rth.parquet`, `_raw.parquet`, `_all.parquet`) for intraday/minute-level data.

**Key Findings:**
- **Total legacy patterns found:** ~15 significant instances across production code
- **Primary hotspots:** Signal generators, demo code, replay engine dailycategory, streamlit app
- **Risk level:** Medium - Some production code paths still construct/expect unsuffixed files
- **Good news:** Core infrastructure (IntradayStore, full_backtest_runner, replay_engine) already updated to support new naming

**Root Cause:** Gradual migration to session-aware naming left some legacy fallbacks and older code paths that weren't updated.

---

## Detailed Findings by Category

### Category A: Direct `{symbol}.parquet` Construction (LEGACY)

**Risk: HIGH** - These paths will fail if only `_rth/_raw` files exist.

| File | Line | Pattern | Risiko |
|------|------|---------|--------|
| `src/signals/cli_inside_bar.py` | 193 | `source = data_path / f"{symbol}.parquet"` | **H** |
| `src/signals/cli_rudometkin_moc.py` | 115 | `source = data_path / f"{symbol}.parquet"` | **H** |
| `src/axiom_bt/intraday.py` | 397 | `m1_file = DATA_M1 / f"{sym}.parquet"` | **H** |
| `src/axiom_bt/demo.py` | 41 | `ohlcv.to_parquet(data_dir / f"{symbol}.parquet")` | M |
| `src/axiom_bt/engines/replay_engine.py` | 513 | `file_path = data_path / f"{symbol}.parquet"` (MOC function) | **H** |
| `apps/streamlit/state.py` | 62-63 | `primary = self.data_dir_m1 / f"{symbol}.parquet"` | **H** |

### Category B: Glob Patterns Expecting Unsuffixed Files

**Risk: MEDIUM** - May miss new files or behave unexpectedly.

| File | Line | Pattern | Risiko |
|------|------|---------|--------|
| `src/signals/cli_inside_bar.py` | 36 | `glob("*.parquet")` for symbol extraction | M |
| `src/axiom_bt/maintenance.py` | 120 | `glob("*.parquet")` for cleanup | M |
| `trading_dashboard/utils/symbol_cache.py` | 39-40 | `glob("*.parquet")` with comment mentioning "AAPL.parquet" | L |

### Category C: Test Code (LOW priority, but should align)

**Risk: LOW** - Tests may pass with old fixtures but fail in production.

| File | Line | Pattern | Note |
|------|------|---------|------|
| `tests/test_axiom_integration.py` | 28, 39 | Creates unsuffixed test files | Update to _rth |
| `tests/test_intraday_store.py` | Multiple | Uses "AAPL.parquet" fixtures | Update to _rth |
| `scripts/generate_test_data.py` | 169 | Generates unsuffixed M1 test data | Update to _rth |

### Category D: Already Fixed (GOOD)

✅ These files already use new naming:
- `src/axiom_bt/engines/replay_engine.py:136-139` - Priority list with `_rth, _raw, _all, unsuffixed`
- `src/axiom_bt/intraday.py:512` - `path_for()` generates `_rth` or `_all` suffix
- `src/axiom_bt/full_backtest_runner.py:105,119` - Generates `bars_exec_M5_rth.parquet`
- `trading_dashboard/repositories/trade_repository.py:61,72` - Globs for `*_rth.parquet`

---

## Top 5 Hotspot Files (by legacy pattern count)

1. **`src/axiom_bt/intraday.py`** - 1 legacy pattern (line 397) ⚠️
2. **`src/signals/cli_inside_bar.py`** - 2 patterns (glob + direct construction) ⚠️
3. **`apps/streamlit/state.py`** - 1 legacy fallback pattern ⚠️
4. **`src/axiom_bt/engines/replay_engine.py`** - 1 legacy (MOC function, line 513) ⚠️
5. **`tests/test_axiom_integration.py`** - 2 test fixtures (low priority)

---

## What is "LEGACY"? (Strict Definition)

**LEGACY** code is any pattern that:
1. Constructs parquet paths as `{SYMBOL}.parquet` WITHOUT `_rth/_raw/_all` suffix
2. Uses `glob("*.parquet")` and expects to match intraday data without suffix awareness
3. Has hardcoded fallback to unsuffixed files BEFORE checking `_rth/_raw`
4. Generates new files with unsuffixed names for M1/M5/M15/H1 data

**NOT LEGACY:**
- Code that uses suffix-aware `path_for(..., session_mode=...)` 
- Code that prioritizes `_rth` then `_raw` then `_all` then unsuffixed (as fallback only)
- Daily data (`D1`) which intentionally uses unsuffixed files
- Documentation/comments mentioning old naming

---

## Minimal Remediation Plan (Read-Only)

**Phase 1: High-Priority Production Code** (Do First)

1. **`src/signals/cli_inside_bar.py:193`**
   - Replace: `source = data_path / f"{symbol}.parquet"`
   - With: `source = store.path_for(symbol, timeframe=Timeframe.M5, session_mode=args.session_mode)`

2. **`src/signals/cli_rudometkin_moc.py:115`**
   - Same pattern as above (use `path_for()`)

3. **`src/axiom_bt/intraday.py:397`**
   - Replace: `m1_file = DATA_M1 / f"{sym}.parquet"`
   - With: `m1_file = self.path_for(sym, timeframe=Timeframe.M1, session_mode="rth")`

4. **`src/axiom_bt/engines/replay_engine.py:513`** (MOC function)
   - Add suffix resolution similar to `_resolve_symbol_path()` or call helper

5. **`apps/streamlit/state.py:62-63`**
   - Replace fallback logic to use `_resolve_symbol_path()` helper or `IntradayStore.path_for()`

**Phase 2: Glob Patterns**

6. **`src/signals/cli_inside_bar.py:36`**
   - Update glob to match both `*.parquet` AND extract symbols intelligently (strip `_rth/_all` suffixes)

7. **`src/axiom_bt/maintenance.py:120`**
   - Update cleanup logic to be suffix-aware

**Phase 3: Test Alignment** (Lower Priority)

8. Update test fixtures to use `_rth` suffix
9. Update `scripts/generate_test_data.py` to generate `_rth` files

---

## Verification Checklist (Post-Fix)

After implementing fixes, verify:

- [ ] No `rg` hits for `f"{symbol}.parquet"` in `src/signals/**` 
- [ ] No `rg` hits for `f"{sym}.parquet"` in `src/axiom_bt/**` (except daily/universe)
- [ ] All M1/M5 data in `artifacts/data_m1/` and `artifacts/data_m5/` uses `_rth` or `_raw` suffix
- [ ] `replay_engine._resolve_symbol_path()` never returns `None` for existing symbols
- [ ] All backtest runs produce `fills_count > 0` for known-good test cases (e.g., HOOD, PLTR)
- [ ] Streamlit app loads charts successfully with new naming
- [ ] No "No data file found for SYMBOL" warnings in logs

---

## Risk Assessment

**Current State:** Medium Risk
- Core backtesting engine (replay_engine) is fixed ✅
- Signal generators still have legacy paths ⚠️
- Dashboard/Streamlit has fallback logic ⚠️

**Post-Remediation:** Low Risk
- All production code uses `path_for()` or `_resolve_symbol_path()`
- No hardcoded unsuffixed construction
- Tests aligned with production naming

---

## Appendix: New Naming Convention (Reference)

**Intraday/Minute Data (M1/M5/M15/H1):**
- `{SYMBOL}_rth.parquet` - Regular Trading Hours only (09:30-16:00 ET)
- `{SYMBOL}_raw.parquet` - All sessions (replaces old `{SYMBOL}_all.parquet`)
- `{SYMBOL}_all.parquet` - Legacy "all sessions" (deprecated, use `_raw`)
- `{SYMBOL}.parquet` - **LEGACY** (unsupported, do not use)

**Daily Data (D1):**
- `{SYMBOL}.parquet` - OK for daily data (no suffix needed)

**Priority Order (in resolvers):**
1. `_rth.parquet` (preferred for strategies)
2. `_raw.parquet` (new standard for "all data")
3. `_all.parquet` (legacy fallback)
4. `.parquet` (legacy fallback, will be removed)
