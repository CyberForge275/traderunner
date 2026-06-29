# Perlentaucher Feature Provider Implementation Plan

Scope:
- external marketdata-stream agent implements feature production
- Traderunner remains consumer-only
- no DB coupling in Traderunner

## Goal

Provide a deterministic, efficient daily feature frame for
`perlentaucher_daily_scan` with these columns:
- `symbol`
- `as_of_date`
- `price_short`
- `price_mid`
- `price_l_long`
- `vol_short`
- `vol_mid`
- `vol_l_long`

## Inputs

Required per symbol, per trading day:
- market date in `America/New_York`
- close
- volume

Minimum history required for a usable row:
- at least `100 + 7 = 107` trading bars

Reason:
- `long` needs 100 bars
- shifted long features need a further 7-bar lookback

## Parameters

- `trend_short_bars = 7`
- `trend_mid_bars = 13`
- `trend_long_bars = 100`
- `trend_long_offset_bars = 7`
- `min_history_days = 107` default fetch floor

Fetch-range rule:
- request always uses `date_to` as the upper bound
- effective `date_from` is resolved to guarantee at least 107 days of history by default
- callers may request a longer range
- callers may not request a shorter range than the configured floor

## Calculation model

For each symbol independently:

1. Sort by trading date ascending.
2. Compute LR slope series on close for windows:
   - 7
   - 13
   - 100
3. Compute LR slope series on volume for windows:
   - 7
   - 13
   - 100
4. Derive:
   - `price_l_long = price_long.shift(7)`
   - `vol_l_long = vol_long.shift(7)`
5. Emit only rows where all required output columns are non-null.

## Numerical method

Do not fit a separate sklearn model for every row.

Use closed-form rolling linear-regression slope:

- let `x = [0, 1, ..., n-1]`
- precompute for each window:
  - `sum_x`
  - `sum_x2`
  - denominator `n * sum_x2 - sum_x^2`
- for each rolling window on `y`:
  - compute `sum_y`
  - compute `sum_xy`
  - slope =
    `(n * sum_xy - sum_x * sum_y) / denominator`

This is the expected performance-safe implementation.

## Delivery shape

Preferred delivery options:

1. In-memory dataframe producer for internal service use
2. HTTP endpoint returning rows keyed by:
   - `symbol`
   - `as_of_date`
3. Optional batch mode:
   - by symbol list
   - by universe
   - by single `as_of_date` or date range

## Suggested endpoint contract

Request:
- `symbols`
- `valid_from`
- `valid_to`
- optional universe selector
- optional parameter override for trend windows

Response rows:
- `symbol`
- `as_of_date`
- `price_short`
- `price_mid`
- `price_l_long`
- `vol_short`
- `vol_mid`
- `vol_l_long`

Optional diagnostics:
- `price_long`
- `vol_long`
- provenance fields

## US symbol derivation plan

Goal:
- provide Perlentaucher candidate feature rows for US common stocks using marketdata-stream as the upstream source of truth

Proposed upstream flow for the external agent:

1. Determine the US symbol universe.
   - Preferred source: marketdata-stream universe membership / symbol master for US stocks
   - Output: normalized uppercase US stock symbol list

2. Fetch or build daily OHLCV for the required symbol set.
   - Input shape: one row per `(symbol, trading_date)`
   - Required columns:
     - `symbol`
     - `trading_date`
     - `open`
     - `high`
     - `low`
     - `close`
     - `volume`

3. Apply minimum history gating before feature emission.
   - Require at least 107 trading bars per symbol to emit a fully usable matcher row

4. Compute rolling slope features per symbol from OHLCV.
   - Price slopes from `close`
   - Volume slopes from `volume`

5. Derive shifted long features.
   - `price_l_long = price_long.shift(7)`
   - `vol_l_long = vol_long.shift(7)`

6. Emit the Perlentaucher feature frame.
   - one row per `(symbol, as_of_date)`
   - required columns:
     - `symbol`
     - `as_of_date`
     - `price_short`
     - `price_mid`
     - `price_l_long`
     - `vol_short`
     - `vol_mid`
     - `vol_l_long`

7. Optional downstream split for Traderunner usage.
   - `candidate_features`: rows for the current target date after US symbol filtering
   - `reference_features`: historical sweet-spot exemplar rows supplied separately or via another selection rule

## Recommended external endpoint sequence

If the external agent wants to keep implementation simple and composable:

1. Endpoint A: return US stock symbols
   - response: normalized symbol list

2. Endpoint B: return daily OHLCV for a symbol list and date range
   - source of truth for all Perlentaucher feature derivation

3. Endpoint C: return derived Perlentaucher feature frame
   - built from Endpoint B or an equivalent internal service layer

Traderunner should consume Endpoint C once available.
Until then, the external side can validate correctness by proving that Endpoint C is deterministically derived from Endpoint B.

## Validation

The produced frame must satisfy Traderunner validation in:
- `src/strategies/perlentaucher_daily_scan/feature_contract.py`

Acceptance checks:
- uppercase symbols
- `YYYY-MM-DD` market dates
- no duplicate `(symbol, as_of_date)`
- no nulls in required output columns
- deterministic results for the same source data

## Performance checklist

- one grouped pass per symbol set, not nested per-row sklearn fits
- reuse rolling computation outputs
- compute long slope once, then shift
- avoid repeated materialization of intermediate large frames when possible
- support filtered-universe execution so prefilter can reduce the candidate set before expensive downstream matching

## Recommended rollout

1. Implement pure feature builder over daily bars.
2. Add unit tests for slope correctness on small deterministic fixtures.
3. Add performance-oriented tests or benchmarks on multi-symbol fixtures.
4. Expose service/API endpoint.
5. Hand Traderunner a sample payload that passes local feature-contract validation.
