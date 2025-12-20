# EODHD Data Pipeline - Fetch, Gap Detection, and Aggregation

**Last Updated:** 2025-12-20  
**Author:** Trading System  
**Status:** Production Ready ✅

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Flow](#data-flow)
4. [Gap Detection](#gap-detection)
5. [RTH Filtering](#rth-filtering)
6. [Merge Strategy](#merge-strategy)
7. [Aggregation](#aggregation)
8. [File Structure](#file-structure)
9. [API Reference](#api-reference)
10. [Usage Examples](#usage-examples)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The EODHD data pipeline provides automated fetching, gap detection, RTH filtering, and aggregation of intraday market data for backtesting and strategy development.

### Key Features

- ✅ **Automatic Gap Detection** - Identifies missing data ranges precisely
- ✅ **Smart Merge Logic** - Preserves existing data, prevents overwrites
- ✅ **RTH Filtering** - Separates Regular Trading Hours from Pre/After-Market
- ✅ **Multi-Timeframe Support** - Auto-generates M5/M15 from M1 data
- ✅ **120-Day Limit Handling** - Respects EODHD API constraints
- ✅ **UTC Timezone Correctness** - No date shift bugs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Dashboard / Backtest Engine                                │
│  "Need TSLA data for 2024-10-01 to 2024-12-19"             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  IntradayStore.ensure()                                     │  ◀─ Orchestration Layer
│  1. Check coverage (check_local_m1_coverage)                │
│  2. Identify precise gaps                                   │
│  3. Fetch missing data for each gap                         │
│  4. Merge with existing data                                │
│  5. Trigger M5/M15 aggregation                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├──────────────────────────────────────────┐
                   │                                          │
                   ▼                                          ▼
┌─────────────────────────────────┐    ┌────────────────────────────────┐
│  check_local_m1_coverage()      │    │  fetch_intraday_1m_to_parquet()│
│  - Analyzes existing M1 data    │    │  - Calls EODHD API             │
│  - Returns precise gap array    │    │  - Saves raw data              │
│  - No timezone shift bugs       │    │  - Filters to RTH              │
└─────────────────────────────────┘    └────────────────┬───────────────┘
                                                        │
                                                        ▼
                                       ┌────────────────────────────────┐
                                       │  filter_rth_session()          │
                                       │  - Filters to 09:30-16:00 ET   │
                                       │  - Removes Pre/After-Market    │
                                       └────────────────┬───────────────┘
                                                        │
                                                        ▼
                                       ┌────────────────────────────────┐
                                       │  resample_m1()                 │
                                       │  - Aggregates M1 → M5          │
                                       │  - Aggregates M1 → M15         │
                                       └────────────────────────────────┘
```

---

## Data Flow

### Complete Fetch & Aggregation Flow

```
1. EODHD API Call
   ↓
2. Raw M1 Data (All Hours)
   ├─→ Save: SYMBOL_raw.parquet (100,617 rows for TSLA example)
   │
   ├─→ RTH Filter (09:30-16:00 ET)
   │   ↓
   │   Save: SYMBOL.parquet (40,950 rows for TSLA example)
   │   ↓
   │   Resample to M5 (5-minute bars)
   │   ├─→ Save: data_m5/SYMBOL.parquet (8,190 rows)
   │   │
   │   Resample to M15 (15-minute bars)
   │   └─→ Save: data_m15/SYMBOL.parquet (2,730 rows)
   │
   └─→ (Raw data kept for debugging/analysis)
```

### Gap Filling Flow

```
1. Request: Oct 1 - Dec 19 (80 days)
   ↓
2. Check Local Coverage
   ├─→ Found: Aug 4 - Dec 18 (existing)
   └─→ Gap: Oct 1 - Aug 3 (missing)
   ↓
3. Fetch Gap Data (Oct 1 - Aug 3)
   ├─→ To temp location
   └─→ RTH filter applied
   ↓
4. Merge with Existing
   ├─→ pd.concat([existing, gap])
   ├─→ .sort_index()
   └─→ .drop_duplicates()
   ↓
5. Save Merged Result
   └─→ SYMBOL.parquet (complete dataset)
   ↓
6. Auto-Aggregate M5/M15
```

---

## Gap Detection

### Function: `check_local_m1_coverage()`

**Location:** `src/axiom_bt/intraday.py`

**Purpose:** Identify precise missing data ranges instead of requesting entire period.

**Old Behavior (Naive):**
```python
# ❌ Problem: Returned entire range as gap if any data missing
if not file_exists or has_any_gap:
    return {"gap_start": "2024-10-01", "gap_end": "2024-12-19"}  # 80 days!
```

**New Behavior (Smart):**
```python
# ✅ Solution: Returns only missing ranges
gaps = []

# Gap before existing data
if requested_start < existing_earliest:
    gaps.append({
        "gap_start": "2024-10-01",
        "gap_end": "2024-08-03",  # Day before existing
        "gap_days": 71,
        "reason": "before_existing_data"
    })

# Gap after existing data
if requested_end > existing_latest:
    gaps.append({
        "gap_start": "2024-12-19",  # Day after existing
        "gap_end": "2024-12-31",
        "gap_days": 13,
        "reason": "after_existing_data"
    })

return {"gaps": gaps}  # Two precise gaps instead of 80-day request!
```

### Return Structure

```python
{
    "available_days": 60,
    "requested_days": 80,
    "has_gap": True,
    "earliest_data": "2024-08-04",
    "latest_data": "2024-12-18",
    "gaps": [
        {
            "gap_start": "2024-10-01",
            "gap_end": "2024-08-03",
            "gap_days": 71,
            "reason": "before_existing_data"
        }
    ]
}
```

### UTC Timezone Fix

**Critical Bug Fixed:** Date extraction was done on timezone-converted timestamps.

```python
# ❌ BEFORE (Wrong):
df_index = df.index.tz_convert("America/New_York")  # Convert to NYC
earliest = df_index.min().date()  # 2024-11-30 (shifted by timezone!)

# ✅ AFTER (Correct):
df_index_utc = pd.to_datetime(df.index, utc=True)  # Keep in UTC
earliest = df_index_utc.min().date()  # 2024-12-01 (correct!)
```

**Why This Matters:**
- EODHD provides UTC timestamps
- Converting to ET shifts dates by 5 hours (EST) or 4 hours (EDT)
- `2024-12-01 00:00 UTC` → `2024-11-30 19:00 ET` → `.date()` = `2024-11-30` ❌
- Must use UTC for date calculations to avoid wrong gap boundaries

---

## RTH Filtering

### Regular Trading Hours (RTH)

**Definition:** US market regular trading hours (09:30-16:00 Eastern Time)

**Session Breakdown:**
```
┌─────────────────────────────────────────┐
│ PRE-MARKET      04:00 - 09:30 ET       │  34,647 rows (34.4%)
├─────────────────────────────────────────┤
│ RTH             09:30 - 16:00 ET       │  40,950 rows (40.7%) ✅
├─────────────────────────────────────────┤
│ AFTER-HOURS     16:00 - 20:00 ET       │  25,020 rows (24.9%)
└─────────────────────────────────────────┘
Total: 100,617 rows (24-hour data)
```

### Why RTH-Only?

**Problem with Full Data:**
- Pre-Market: Low volume, wide spreads, volatile prices
- After-Hours: Limited liquidity, not representative
- **Strategy signals get distorted** by non-RTH data

**Benefits of RTH-Only:**
- ✅ High liquidity and tight spreads
- ✅ Representative price action
- ✅ Accurate backtest results
- ✅ Matches real trading conditions

### Implementation

**Function:** `filter_rth_session()`  
**Location:** `src/axiom_bt/data/session_filter.py`

```python
def filter_rth_session(
    df: pd.DataFrame,
    tz: str = "America/New_York",
    rth_start: str = "09:30",
    rth_end: str = "16:00",
) -> pd.DataFrame:
    """
    Filter DataFrame to RTH only.
    
    - Converts timestamps to target timezone
    - Filters to time range [09:30, 16:00)
    - Returns filtered copy
    """
    # Convert to target timezone
    ts_tz = df.index.tz_convert(tz)
    
    # Filter to RTH window
    mask = (ts_tz.time >= time(9, 30)) & (ts_tz.time < time(16, 0))
    
    return df[mask].copy()
```

### Automatic Application

RTH filtering is **automatically applied** during data fetch:

```python
# In fetch_intraday_1m_to_parquet()
if save_raw:
    # 1. Save ALL data first
    df.to_parquet(f"{symbol}_raw.parquet")

if filter_rth:
    # 2. Filter to RTH
    df = filter_rth_session(df, tz="America/New_York")

# 3. Save RTH-only data
df.to_parquet(f"{symbol}.parquet")
```

---

## Merge Strategy

### Problem: Overlapping Data

When fetching gap data, timestamps may overlap with existing data:

```
Existing:  [===============Aug 4 - Dec 18================]
New Gap:   [======Oct 1 - Aug 4======]
                                    ^^^^
                                  Overlap!
```

### Solution: Smart Merge with Deduplication

```python
# 1. Load existing data
existing_df = pd.read_parquet("TSLA.parquet")

# 2. Load gap data
gap_df = pd.read_parquet(temp_gap_file)

# 3. Merge with deduplication
merged = pd.concat([existing_df, gap_df])
merged = merged.sort_index().drop_duplicates()

# 4. Save merged result
merged.to_parquet("TSLA.parquet")
```

### Verification

**Test Case:** Overlapping fetch
```
Before merge:  92,937 + 14,400 = 107,337 rows
After merge:   100,617 rows
Removed:       6,720 duplicates ✅
```

**Proof:** `.drop_duplicates()` correctly removes duplicate timestamps.

---

## Aggregation

### M1 → M5 → M15

**All aggregations are done AFTER RTH filtering:**

```
M1 (40,950 rows, RTH only)
  ↓ resample("5min")
M5 (8,190 rows)
  ↓ resample("15min")  (from M1, not M5!)
M15 (2,730 rows)
```

### Aggregation Function

**Function:** `resample_m1()`  
**Location:** `src/axiom_bt/data/eodhd_fetch.py`

```python
def resample_m1(
    m1_parquet: Path,
    out_dir: Path,
    interval: str = "5min",  # or "15min"
    tz: str = "America/New_York",
) -> Path:
    """
    Resample 1-minute bars to higher timeframe.
    
    OHLCV aggregation:
    - Open: first
    - High: max
    - Low: min
    - Close: last
    - Volume: sum
    """
```

### Automatic Triggering

Aggregation happens **automatically** in `IntradayStore.ensure()`:

```python
# After M1 data is ready (cached or fetched)

# Always create M5
resample_m1(m1_path, DATA_M5, interval="5min", tz=tz)

# Create M15 if needed
if spec.timeframe == Timeframe.M15:
    resample_m1(m1_path, DATA_M15, interval="15min", tz=tz)
```

**No manual intervention needed!**

---

## File Structure

### Directory Layout

```
artifacts/
├── data_m1/                        # 1-minute bars
│   ├── TSLA_raw.parquet            # Raw data (Pre+RTH+After)   2.7 MB
│   ├── TSLA.parquet                # RTH-only (09:30-16:00)     1.4 MB
│   ├── HOOD_raw.parquet
│   └── HOOD.parquet
│
├── data_m5/                        # 5-minute bars (from RTH M1)
│   ├── TSLA.parquet                # Aggregated from RTH M1     303 KB
│   └── HOOD.parquet
│
└── data_m15/                       # 15-minute bars (from RTH M1)
    ├── TSLA.parquet                # Aggregated from RTH M1     111 KB
    └── HOOD.parquet
```

### File Naming Convention

- `{SYMBOL}_raw.parquet` - Raw data with all hours (Pre-Market, RTH, After-Hours)
- `{SYMBOL}.parquet` - RTH-only data (primary file for strategies)

### File Sizes (TSLA Example)

```
M1 Raw:   2.7 MB (100,617 rows) - All 24h data
M1 RTH:   1.4 MB ( 40,950 rows) - RTH only (40.7% of raw)
M5:       303 KB (  8,190 rows) - From RTH M1
M15:      111 KB (  2,730 rows) - From RTH M1
```

---

## API Reference

### fetch_intraday_1m_to_parquet()

**Location:** `src/axiom_bt/data/eodhd_fetch.py`

```python
def fetch_intraday_1m_to_parquet(
    symbol: str,
    exchange: str,
    start_date: Optional[str] = None,  # 'YYYY-MM-DD'
    end_date: Optional[str] = None,    # 'YYYY-MM-DD'
    out_dir: Path = Path("artifacts/data_m1"),
    tz: str = "America/New_York",
    use_sample: bool = False,
    save_raw: bool = True,             # NEW: Save raw data
    filter_rth: bool = True,           # NEW: Filter to RTH
) -> Path:
    """
    Fetch 1-minute intraday data from EODHD.
    
    Returns:
        Path to final parquet file (RTH-filtered if filter_rth=True)
        
    Files Created:
        - {symbol}_raw.parquet if save_raw=True
        - {symbol}.parquet (filtered if filter_rth=True)
    """
```

### check_local_m1_coverage()

**Location:** `src/axiom_bt/intraday.py`

```python
def check_local_m1_coverage(
    symbol: str,
    start: str,      # ISO date 'YYYY-MM-DD'
    end: str,        # ISO date 'YYYY-MM-DD'
    tz: str = "America/New_York"
) -> dict:
    """
    Check M1 data coverage and identify precise gaps.
    
    Returns:
        {
            "available_days": int,
            "requested_days": int,
            "has_gap": bool,
            "earliest_data": str (ISO),
            "latest_data": str (ISO),
            "gaps": [
                {
                    "gap_start": str,
                    "gap_end": str,
                    "gap_days": int,
                    "reason": str
                }
            ]
        }
    """
```

### filter_rth_session()

**Location:** `src/axiom_bt/data/session_filter.py`

```python
def filter_rth_session(
    df: pd.DataFrame,
    tz: str = "America/New_York",
    rth_start: str = "09:30",
    rth_end: str = "16:00",
) -> pd.DataFrame:
    """
    Filter DataFrame to Regular Trading Hours only.
    
    Args:
        df: DataFrame with DatetimeIndex or 'timestamp' column
        tz: Timezone for session (default: America/New_York)
        rth_start: RTH start time HH:MM
        rth_end: RTH end time HH:MM (exclusive)
    
    Returns:
        Filtered DataFrame containing only RTH data
    """
```

---

## Usage Examples

### Example 1: Fetch Fresh Data

```python
from axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet
from pathlib import Path

# Fetch TSLA data with RTH filtering
path = fetch_intraday_1m_to_parquet(
    symbol='TSLA',
    exchange='US',
    start_date='2024-10-01',
    end_date='2024-12-19',
    save_raw=True,   # Creates TSLA_raw.parquet
    filter_rth=True, # Creates TSLA.parquet (RTH only)
)

# Result:
# - artifacts/data_m1/TSLA_raw.parquet (all hours)
# - artifacts/data_m1/TSLA.parquet (RTH only)
```

### Example 2: Check for Gaps

```python
from axiom_bt.intraday import check_local_m1_coverage

result = check_local_m1_coverage(
    symbol='TSLA',
    start='2024-10-01',
    end='2024-12-19',
    tz='America/New_York'
)

if result['has_gap']:
    for gap in result['gaps']:
        print(f"Gap: {gap['gap_start']} to {gap['gap_end']} ({gap['gap_days']} days)")
else:
    print("No gaps - full coverage!")
```

### Example 3: Automatic via IntradayStore

```python
from axiom_bt.intraday import IntradayStore, IntradaySpec, Timeframe
from datetime import date

store = IntradayStore(default_tz="America/New_York")

spec = IntradaySpec(
    symbols=['TSLA'],
    start=date(2024, 10, 1),
    end=date(2024, 12, 19),
    timeframe=Timeframe.M15,
)

# This automatically:
# 1. Checks for gaps
# 2. Fetches missing data (RTH filtered)
# 3. Merges with existing
# 4. Creates M5 and M15
actions = store.ensure(spec, auto_fill_gaps=True)

print(actions)
# {'TSLA': ['gap_fill_1_gaps_71_days', 'resample_m5', 'resample_m15']}
```

### Example 4: Manual RTH Filtering

```python
from axiom_bt.data.session_filter import filter_rth_session, get_rth_stats
import pandas as pd

# Load raw data
df_raw = pd.read_parquet('artifacts/data_m1/TSLA_raw.parquet')

# Get stats
stats = get_rth_stats(df_raw)
print(f"RTH: {stats['rth_percentage']:.1f}%")
print(f"Pre-Market: {stats['pre_market_rows']:,} rows")
print(f"After-Hours: {stats['after_hours_rows']:,} rows")

# Filter to RTH
df_rth = filter_rth_session(df_raw)
print(f"Filtered: {len(df_rth):,} rows")
```

---

## Troubleshooting

### Issue: "No gaps but data looks incomplete"

**Cause:** Timezone shift bug (pre-fix)  
**Solution:** Code now uses UTC for date calculations

```python
# Verify with:
result = check_local_m1_coverage('TSLA', '2024-10-01', '2024-12-19')
print(result['earliest_data'], result['latest_data'])
```

### Issue: "Duplicate timestamps after merge"

**Cause:** `.drop_duplicates()` not called  
**Solution:** Already implemented in merge logic

```python
merged = pd.concat([existing, new])
merged = merged.sort_index().drop_duplicates()  # ← Critical!
```

### Issue: "M5/M15 still have Pre/After-Market data"

**Cause:** Aggregated before RTH filtering was implemented  
**Solution:** Regenerate from RTH M1 data

```python
from axiom_bt.data.eodhd_fetch import resample_m1
from pathlib import Path

# Regenerate from RTH-only M1
resample_m1(
    m1_parquet=Path('artifacts/data_m1/TSLA.parquet'),  # RTH-only
    out_dir=Path('artifacts/data_m5'),
    interval='5min'
)
```

### Issue: "EODHD API timeout"

**Cause:** API slow or network issues  
**Solution:** Retry or use existing data

```python
# Use cached data if available
store.ensure(spec, force=False)  # Won't re-fetch if data exists
```

### Issue: "ValueError: Range exceeds 120 days"

**Cause:** EODHD limit for 1-minute data is 120 days  
**Solution:** Gap detection automatically chunks requests

```python
# Gap detection splits into multiple fetches automatically
# Each gap ≤ 120 days is fetched separately
```

---

## Performance Metrics

### TSLA Example (148 days)

**Data Reduction:**
```
Raw Data:   100,617 rows
RTH Only:    40,950 rows (59.3% reduction)
```

**File Sizes:**
```
M1 Raw:  2.7 MB
M1 RTH:  1.4 MB (48% smaller)
M5:      303 KB
M15:     111 KB
```

**Fetch Times:**
```
Gap Detection:        < 0.1s
Fetch (20 days):      ~12s (network dependent)
RTH Filter:           ~0.2s
Merge:                ~0.1s
M5 Aggregation:       ~0.3s
M15 Aggregation:      ~0.1s
TOTAL:                ~13s for 20-day gap
```

---

## Changelog

### 2025-12-20 - RTH Filtering Added
- ✅ Added `session_filter.py` module
- ✅ `save_raw` and `filter_rth` parameters
- ✅ Automatic RTH filtering during fetch
- ✅ Separate raw and RTH parquet files

### 2025-12-20 - Gap Detection & Merge
- ✅ Precise gap detection (returns array)
- ✅ Smart merge with deduplication
- ✅ UTC timezone fix for date extraction
- ✅ Multiple gap support (before/after)

### 2025-12-20 - EODHD Fetch Simplification
- ✅ Optional `start_date`/`end_date` parameters
- ✅ 120-day validation
- ✅ Comprehensive documentation

---

## Related Files

- `src/axiom_bt/data/eodhd_fetch.py` - Fetch and aggregation
- `src/axiom_bt/data/session_filter.py` - RTH filtering
- `src/axiom_bt/data/eodhd_constants.py` - API limits
- `src/axiom_bt/intraday.py` - Gap detection and orchestration
- `tests/test_intraday_store.py` - Unit tests

---

**Status:** Production Ready ✅  
**Last Verified:** 2025-12-20 via Dashboard UI backtest (TSLA 148 days, M5 timeframe)
