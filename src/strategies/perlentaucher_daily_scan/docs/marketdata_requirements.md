# Perlentaucher Marketdata Requirements

This file defines the inbound SSOT payload expected by Traderunner for
`perlentaucher_daily_scan`.

Scope:
- Traderunner strategy consumes this payload only as injected data
- no direct DB access
- no direct dependency on `marketdata-monorepo`

## Required dataset

Marketdata-stream must provide a daily feature frame keyed by:
- `symbol`
- `as_of_date`

Required columns:
- `symbol`
- `as_of_date`
- `price_short`
- `price_mid`
- `price_l_long`
- `vol_short`
- `vol_mid`
- `vol_l_long`

## Column semantics

- `symbol`: uppercase ticker symbol
- `as_of_date`: market session date in `America/New_York`, formatted `YYYY-MM-DD`
- all feature columns: numeric `float`

## Feature calculation rules

Price features must use:
- raw `close` from OHLCV

Volume features must use:
- raw volume

Trend windows:
- `trend_short_bars = 7`
- `trend_mid_bars = 13`
- `trend_long_bars = 100`
- `trend_long_offset_bars = 7`

Minimum fetch window:
- `min_history_days = 107` by default
- this may only be increased, never reduced below 107

Derived feature definitions for each `(symbol, as_of_date)`:
- `price_short`: linear-regression slope of close over the last 7 trading bars ending at `as_of_date`
- `price_mid`: linear-regression slope of close over the last 13 trading bars ending at `as_of_date`
- `price_long`: linear-regression slope of close over the last 100 trading bars ending at `as_of_date`
- `vol_short`: linear-regression slope of volume over the last 7 trading bars ending at `as_of_date`
- `vol_mid`: linear-regression slope of volume over the last 13 trading bars ending at `as_of_date`
- `vol_long`: linear-regression slope of volume over the last 100 trading bars ending at `as_of_date`
- `price_l_long`: `price_long` shifted by 7 trading bars into the future lookup space
  - equivalent: for date `D`, use `price_long` from `D - 7 trading bars`
- `vol_l_long`: `vol_long` shifted by 7 trading bars into the future lookup space
  - equivalent: for date `D`, use `vol_long` from `D - 7 trading bars`

Matcher-required output columns remain:
- `price_short`
- `price_mid`
- `price_l_long`
- `vol_short`
- `vol_mid`
- `vol_l_long`

`price_long` and `vol_long` may be emitted as optional diagnostics but are not required by Traderunner matcher input.

## Contract rules

- one row per `(symbol, as_of_date)`
- no duplicate key rows
- no nulls in required columns
- timestamps and date derivation must respect market timezone `America/New_York`
- payload must be deterministic for the same upstream data cut

## Intended usage in Traderunner

Traderunner uses two injected frames:

1. `reference_features`
   - historical sweet-spot exemplars
   - used to build native and z-score matching ranges

2. `candidate_features`
   - current daily candidate rows for the target `as_of_date`
   - used for matching and ranking

## Acceptance expectations for the external agent

- emitted frame validates against
  `src/strategies/perlentaucher_daily_scan/feature_contract.py`
- values are reproducible for the same input data
- no DB-specific assumptions leak into Traderunner strategy code
- computation must remain efficient for large symbol universes

## Performance constraints

The implementation must be vectorized or near-vectorized across symbols.

Avoid:
- Python loops over every rolling window for every symbol
- repeated sklearn model fitting per row
- recomputing the same slope series multiple times for the same symbol

Preferred approach:
- sort by `symbol, as_of_date`
- compute rolling linear-regression slopes with a closed-form formula
- reuse precomputed constants for each window length
- compute `price_long` and `vol_long` once, then derive `price_l_long` / `vol_l_long` via grouped shift

Minimum expectation:
- suitable for running across the filtered daily universe without per-symbol model-instantiation overhead
