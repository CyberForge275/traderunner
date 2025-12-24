# PROJECT STATE - Pre-INT Debug Deploy

**Date:** 2025-12-19 12:30 CET
**Purpose:** Audit-ready snapshot before November parity restoration and INT debug deployment

---

## Git State

**Current Commit:** `a6a51fb`
**Branch:** `feature/enterprise-metadata-ssot`
**Backup Branch:** `backup/pre_int_debug_2025-12-19`
**Backup Tag:** `pre_int_debug_2025-12-19`

**Working Tree:** Clean ✅

**Recent Changes:**
- Session filter timezone fix (f9f90e0)
- Debug logging added (a6a51fb)
- Timezone columns in orders.csv (ebc0a66)
- UI timezone indicators (8772a5b)

---

## Configuration

### Session Filter (Active)
```python
session_timezone = "America/New_York"
session_windows = ["09:30-16:00"]  # Default for US markets
# UI can override with custom windows
```

### Order Validity
```python
order_validity_policy = "one_bar"
valid_from_policy = "signal_ts"
```

---

## Golden Master Reference

**November Baseline Run:**
```
Path: run_20251127_120221_ui_m5_APP_360d_10k/orders.csv
Date: 2025-11-27
Symbol: AAPL
Timeframe: M5
Result: Successful fills + trades generation
```

**Key Characteristics:**
- Orders generated with filled flags
- Trades.csv created
- Replay engine successfully simulated fills

---

## Environment

### Python
```
Version: 3.12.3
Location: /home/mirko/data/workspace/droid/traderunner
```

### Key Dependencies (pip freeze extract)
```
pandas==2.2.3
numpy==2.2.1
pytz==2025.1
plotly==5.24.1
dash==2.19.1
```

---

## Known Issues

### 1. Session Filter Timezone Bug
**Status:** Partially fixed (f9f90e0)
**Issue:** `is_in_session()` called without `tz` parameter → uses default Europe/Berlin
**Fix Applied:** Added `session_tz` parameter to final filter (line 619)
**Remaining:** Pattern detection filter needs verification

### 2. INT vs DEV Divergence
**Status:** Under investigation
**Symptom:** 50% of orders outside configured session windows on INT
**Local Test:** Session filter works correctly (0 orders outside windows)
**Hypothesis:** INT running different code version or config parsing issue

### 3. OHLCV Column Case Sensitivity
**Status:** To be addressed
**Issue:** EODHD data has lowercase columns, some code expects uppercase
**Risk:** Duplicate columns (Open+open) or NaN propagation
**Plan:** Enforce lowercase everywhere, add normalization guardrails

---

## Recent Artifacts

### Backtests
```
Latest: 251219_104825_HOOD_Final
Result: 10 orders, 5 outside session windows (NO-GO)
Config: session_windows=["10:00-11:00", "14:00-15:00"]
```

### Reports
- `/home/mirko/.gemini/.../session_filter_fix_failure.md` (NO-GO analysis)
- `/home/mirko/.gemini/.../session_filter_behavior.md` (Filter logic documentation)

---

## Rollback Procedure

If needed to restore this exact state:

```bash
cd /home/mirko/data/workspace/droid/traderunner
git checkout pre_int_debug_2025-12-19
# Or: git checkout backup/pre_int_debug_2025-12-19
```

**Verification:**
```bash
git rev-parse HEAD  # Should be: a6a51fb
git status          # Should be: clean
```

---

## Next Steps (Planned)

1. ✅ Secure project state (this document)
2. ⏳ Implement lowercase OHLCV normalization
3. ⏳ Extend debug logging (OHLCV + metadata)
4. ⏳ Deploy to INT with commit verification
5. ⏳ Run INT test with debug logging
6. ⏳ INT vs DEV comparison report

---

**Commit Hash (for audit):** `a6a51fb`
**Author:** mirko2175
**State Captured:** 2025-12-19 12:30:00 CET
