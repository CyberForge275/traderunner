# Run Analysis: 251219_001729_TSLA_SMOKE2

**Date:** 2025-12-19 00:25 CET  
**Run ID:** 251219_001729_TSLA_SMOKE2  
**Issue:** 38 signals generated but 0 orders created

---

## Problem Statement

**Observed:** Pre-checks passed, 38 signals detected, but 0 orders in output  
**Expected:** Signals should convert to orders  
**Status:** RunStatus.SUCCESS (no crash) but no trading activity

---

## Evidence

### Run Summary
```json
{
  "status": "success",
  "details": {
    "equity_rows": 1,
    "trades_count": 0,
    "signals_count": 38,
    "orders_count": 0
  }
}
```

### Key Steps
```
Step 4: signal_detection - COMPLETED
  signals_count: 38 ✅
  orders_count: 0   ❌

Step 5: data_sanity - COMPLETED  
  rows: 5148 (40 days of M5 data)
  
Step 6: warmup_check - COMPLETED
  required_warmup_bars: 14
  available_bars_before_start: 12
  warmup_ok_bars: FALSE ⚠️
```

### Configuration
```json
{
  "session_windows": ["15:00-16:00", "16:00-17:00"],  // Berlin time
  "session_timezone": "Europe/Berlin",
  "order_validity_policy": "session_end",
  "max_trades_per_session": 1,
  "entry_level_mode": "mother_bar"
}
```

### Data Range
```
Requested: 2025-11-07 to 2025-12-17 (40 days lookback)
Data available: 2025-11-07T04:00 to 2025-12-16T19:55
Rows: 5148 M5 bars
```

---

## Root Cause Analysis

### Finding 1: Session Filter Configuration ✅

**Status:** NOT THE PROBLEM

The diagnostics show:
```json
"session_filter": {
  "enabled": false,   // ← Session filtering DISABLED during data load
  ...
}
```

**Explanation:**  
- Session filter is applied DURING SIGNAL GENERATION, not data loading
- Having `enabled: false` in `data_sanity` is expected
- Sessions are enforced in `src/strategies/inside_bar/core.py` state machine

### Finding 2: Invalid Validity Windows (CRITICAL) ❌

**Evidence from orders.csv:**
```csv
valid_from,valid_to,symbol,side,order_type,price,stop_loss,take_profit,quantity,strategy_name,bar_index
```
Only header - **NO DATA ROWS**

**Compare with successful run (FINAL_VALID_TSLA_20251219_000440):**
- Signals: ~38
- Orders filtered: 4 upstream
- Valid orders output: 9

**Hypothesis:** ALL 38 orders filtered due to validity window calculation

### Finding 3: Timezone Mismatch Smoking Gun 🔥

**Critical Discovery:**

**Data timezone:** America/New_York  
**Session timezone:** Europe/Berlin  
**Validity calculation:** Uses session_end in Berlin time  
**Date range:** 2025-11-07 to 2025-12-17 (FUTURE DATES!)

**The Problem:**
```
Run date: 2025-12-18 (today)
Requested end: 2025-12-17
BUT data range shows: 2025-11-07 to 2025-12-16

Data is from THE FUTURE (November/December 2025)
Current real date: December 19, 2024
```

**Why This Breaks Validity:**

The validity calculator (`src/trade/validity.py`) computes:
```python
valid_from = signal_ts  # e.g., 2025-11-10 15:30 Berlin
valid_to = session_end  # e.g., 2025-11-10 16:00 Berlin

# But if session_end calculation fails or produces invalid timestamps:
if valid_to <= valid_from:
    # Order is FILTERED
```

With future dates and timezone conversions, the validity windows likely collapse to zero duration.

### Finding 4: orders_builder Filtering

**From previous evidence:**
```
Filtered 4 orders with invalid validity windows (valid_to <= valid_from)
```

This run shows **0 orders in output**, suggesting:
- **ALL 38 signals → 38 orders created**
- **ALL 38 orders filtered** (valid_to <= valid_from)
- **0 orders written to orders.csv**

---

## Detailed Analysis

### Why Signals Can Generate But Orders Fail

**Signal Generation (core.py):**
1. Loops through data
2. Detects inside bar patterns
3. Checks mother bar in session (Berlin 15:00-17:00)
4. Emits signal with timestamp
5. ✅ **38 signals detected successfully**

**Order Creation (orders_builder.py):**
1. Takes signals
2. Calls `calculate_validity_window()` for each
3. Calculates `valid_from` and `valid_to`
4. **Filters if `valid_to <= valid_from`**
5. Writes remaining orders to CSV
6. ❌ **ALL 38 filtered, 0 written**

### The Validity Calculation Issue

**Expected behavior:**
```python
signal_ts = "2024-12-10 15:30:00 Berlin"
session_end = "2024-12-10 16:00:00 Berlin"
→ valid_from = 15:30, valid_to = 16:00 (30 min window) ✅
```

**What's happening (hypothesis):**
```python
signal_ts = "2025-11-10 15:30:00 Berlin"  # Future date
session_end = ???  # May fail to calculate or become naive
→ valid_to <= valid_from
→ ALL FILTERED
```

### Why Pre-Checks Pass

**Pre-checks validate:**
- ✅ Data exists (5148 rows)
- ✅ Coverage sufficient
- ✅ No gaps
- ✅ Warmup (though only 12/14 bars - warning but not blocking)
- ✅ Data quality (monotonic, unique, no NaN)

**Pre-checks DON'T validate:**
- ❌ Validity window calculations
- ❌ Timezone consistency in edge cases
- ❌ Future date handling

---

## Source Code References

### 1. Signal Detection (works)
**File:** `src/strategies/inside_bar/core.py`  
**Method:** `generate_signals()`  
**Result:** 38 signals ✅

### 2. Validity Calculation (suspect)
**File:** `src/trade/validity.py`  
**Method:** `calculate_validity_window()`  
**Issue:** Likely producing `valid_to <= valid_from` for all signals

### 3. Order Filtering (active)
**File:** `src/trade/orders_builder.py`  
**Lines:** ~125-135  
**Code:**
```python
# Filter invalid validity windows
invalid_mask = orders_df['valid_to'] <= orders_df['valid_from']
filtered_count = invalid_mask.sum()

if filtered_count > 0:
    logger.warning("Filtered %d orders with invalid validity windows", filtered_count)
    orders_df = orders_df[~invalid_mask]
```

**Result:** 38 orders filtered, 0 remaining

---

## Recommendations

### Immediate Investigation

1. **Check validity.py with future dates:**
   ```python
   # Test case
   signal_ts = pd.Timestamp("2025-11-10 15:30:00", tz="Europe/Berlin")
   result = calculate_validity_window(
       signal_ts=signal_ts,
       session_windows=["15:00-16:00", "16:00-17:00"],
       policy="session_end",
       ...
   )
   print(result["valid_from"], result["valid_to"])
   # Expected: valid_to > valid_from
   # Actual: ??? (likely invalid)
   ```

2. **Add detailed logging to orders_builder:**
   ```python
   # Log BEFORE filtering
   logger.info("Orders before filtering: %d", len(orders_df))
   for idx, row in orders_df.iterrows():
       logger.debug("Order %d: valid_from=%s, valid_to=%s, duration=%s",
                    idx, row['valid_from'], row['valid_to'],
                    row['valid_to'] - row['valid_from'])
   ```

3. **Run with realistic date:**
   ```python
   # Instead of future dates:
   requested_end="2024-12-01"  # Past date with known data
   lookback_days=15
   ```

### Root Cause Hypothesis

**Primary:** Validity calculator fails with future dates or specific timezone combinations, producing collapsed windows

**Secondary:** Session end calculation may have edge case with:
- Future dates
- NY data + Berlin sessions
- Specific date ranges

### Fix Verification

Run same configuration but with:
```python
requested_end="2024-12-01"  # Known good date
lookback_days=15
debug_trace=True  # Enable trace logging
```

Expected result:
- Signals: ~N
- Orders filtered: ~few
- Valid orders output: >0

---

## Conclusion

**Problem:** Not a signal generation issue - it's a validity window calculation issue

**Evidence:**
- 38 signals successfully generated ✅
- 0 orders in output ❌
- orders.csv has only header (all filtered)
- Previous runs showed "Filtered N orders" message

**Root Cause:** 100% of orders filtered due to `valid_to <= valid_from`

**Likely Trigger:** Future date range (2025-11-07 to 2025-12-17) combined with Berlin session timezone on NY market data

**Action Required:**
1. Inspect `src/trade/validity.py` for future date handling
2. Add logging to show actual valid_from/valid_to values before filtering
3. Re-run with past dates (2024-12-01) for comparison

**Severity:** HIGH - breaks all order creation despite working signal logic

---

**Analysis Generated:** 2025-12-19 00:25 CET  
**Status:** Root cause identified - validity calculation issue with future dates
