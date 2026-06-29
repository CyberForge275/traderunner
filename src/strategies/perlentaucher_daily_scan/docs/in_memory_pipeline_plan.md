# Perlentaucher In-Memory Pipeline Plan

Goal:
- consume daily OHLCV in memory only
- do not persist local files
- minimize memory and CPU before slope and matcher work

## Recommended execution order

1. fetch daily OHLCV universe snapshot
2. normalize and prune columns
3. run daily prefilter
4. restrict to surviving symbols only
5. compute slope-based feature frame
6. run matcher and ranking
7. return ranked signals/candidates

## Proposed module layout

All files remain under:
- `src/strategies/perlentaucher_daily_scan/`

Recommended new modules:
- `daily_pipeline.py`
- `slope_features.py`
- optional Spyder runner:
  - `tools/run_in_memory_daily_scan_spyder.py`

## Stage responsibilities

### 1. Fetch stage

Input:
- HTTP response from marketdata-stream daily merged parquet endpoint

Output:
- `daily_df`

Required columns:
- `symbol`
- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`

Rules:
- keep only these columns immediately
- uppercase symbols
- parse `date`
- sort by `symbol`, `date`

### 2. Prefilter stage

Module:
- existing `prefilter.py`

Input:
- `daily_df`

Output:
- `prefilter_metrics_df`
- `candidate_symbols`

Rules:
- compute only one final row per symbol for the target `as_of_date`
- do not compute slope features yet

### 3. Candidate subset stage

Input:
- `daily_df`
- `candidate_symbols`

Output:
- `candidate_daily_df`

Rules:
- keep only rows for surviving symbols
- this is the main CPU/memory reduction step before slope work

### 4. Slope feature stage

New module:
- `slope_features.py`

Input:
- `candidate_daily_df`
- target `as_of_date`
- trend parameters:
  - `7 / 13 / 100`
  - `long_offset = 7`

Output:
- `feature_df`

Columns:
- `symbol`
- `as_of_date`
- `price_short`
- `price_mid`
- `price_l_long`
- `vol_short`
- `vol_mid`
- `vol_l_long`

Rules:
- compute grouped rolling LR slopes on `close`
- compute grouped rolling LR slopes on `volume`
- derive long-shift features via grouped shift
- only emit rows for the target `as_of_date`

### 5. Matcher stage

Modules:
- existing `reference_set.py`
- existing `matcher.py`

Input:
- `feature_df`
- injected `reference_features`

Output:
- `matched_df`

Rules:
- validate feature contract first
- rank deterministically

## Proposed function names

### `daily_pipeline.py`

- `normalize_daily_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame`
- `select_prefilter_candidate_symbols(daily_df: pd.DataFrame, *, as_of_date: str) -> pd.DataFrame`
- `filter_daily_frame_to_candidates(daily_df: pd.DataFrame, candidate_symbols: pd.Series) -> pd.DataFrame`
- `run_in_memory_daily_scan(daily_df: pd.DataFrame, *, as_of_date: str, reference_features: pd.DataFrame, params: dict) -> pd.DataFrame`

### `slope_features.py`

- `compute_lr_slope_series(values: pd.Series, window: int) -> pd.Series`
- `build_slope_feature_frame(daily_df: pd.DataFrame, *, as_of_date: str, short_window: int = 7, mid_window: int = 13, long_window: int = 100, long_offset: int = 7) -> pd.DataFrame`

## Memory strategy

### Keep only required columns

After fetch, immediately project to:
- `symbol`
- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`

### Use lighter dtypes where safe

- `symbol`: category if cardinality is large
- numeric columns: `float32` can be considered for `open/high/low/close/volume`
- slope outputs: prefer `float64`

### Avoid repeated full-frame copies

- prefer narrow projections
- drop intermediates once no longer needed
- avoid storing multiple “almost identical” versions of the same universe frame

## CPU strategy

- prefilter before slope calculation
- no sklearn fit per row
- no Python nested loop over windows
- use closed-form rolling LR slope
- compute long slopes once and reuse with grouped shift

## Spyder workflow recommendation

For manual research/debugging:

1. fetch OHLCV to `daily_df`
2. inspect memory and row counts
3. run prefilter and inspect candidate count
4. build `feature_df`
5. inspect latest rows for the target date
6. run matcher

Recommended variables to expose in Spyder:
- `daily_df`
- `prefilter_metrics_df`
- `candidate_daily_df`
- `feature_df`
- `matched_df`

## First implementation target

Implement first:
- `slope_features.py`
- `daily_pipeline.py`

Then add:
- `tools/run_in_memory_daily_scan_spyder.py`

This gives a full in-memory research path before any production integration.
