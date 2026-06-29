# NDX Momentum Rotation - ROC60 Top10 Report

Date: 2026-03-27  
Repo: `traderunner`  
Commit baseline: `c94851b`

## Scope
Implemented the bottom-up research slice only:
- resolve NDX members for a date via `marketdata-stream`
- load daily bars from local parquet
- compute `ROC60`
- rank deterministic Top10

No rebalance logic, no regime logic, no allocation, no intents.

## Files changed
- `src/axiom_bt/pipeline/marketdata_stream_client.py`
- `src/strategies/ndx_momentum_rotation/universe.py`
- `src/strategies/ndx_momentum_rotation/scoring.py`
- `src/strategies/ndx_momentum_rotation/ranking.py`
- `src/strategies/ndx_momentum_rotation/tools/run_universe_resolution_spyder.py`
- `src/strategies/ndx_momentum_rotation/tools/run_roc60_top10_spyder.py`
- `src/strategies/ndx_momentum_rotation/tests/test_universe.py`
- `src/strategies/ndx_momentum_rotation/tests/test_scoring.py`
- `tests/test_fetch_universe_members_tool.py`
- `tools/fetch_universe_members.py`

## Tests
Command:
```bash
PYTHONPATH=src:. pytest -q \
  src/strategies/ndx_momentum_rotation/tests/test_scoring.py \
  src/strategies/ndx_momentum_rotation/tests/test_universe.py \
  tests/test_fetch_universe_members_tool.py -q
```

Result:
- `11 passed`

## Important bug found during verification
Initial ROC60 implementation used `as_of_date` as `UTC midnight`.
That was wrong for daily bars normalized to `America/New_York`.
Effect:
- the ranker used the previous session instead of the requested market date
- observed symptom: top rows had timestamp `2026-03-24 04:00:00+00:00` for `as_of_date=2026-03-25`

Fix:
- `build_roc_scores(...)` now filters by market session date using `session_timezone`
- RED test added in `src/strategies/ndx_momentum_rotation/tests/test_scoring.py`

## Verification inputs
Universe source:
- `POST /universe/members`
- payload:
```json
{"universe":"NDX","as_of_date":"2026-03-25","survivorship_mode":"current_members"}
```

Bars source:
- `data/universe/stocks_data.parquet`

Scoring params:
- `lookback_bars = 60`
- `top_n = 10`
- `session_timezone = America/New_York`

## Verification results
### Universe resolution
- endpoint rows: `101`
- endpoint unique symbols: `101`
- valid members with daily bar on `2026-03-25`: `96`
- missing from local daily parquet on requested date: `FER, PLTR, SHOP, TRI, WMT`

Interpretation:
- the universe API is returning a broader current-members set than the local parquet can satisfy on the requested date
- strategy-side intersection is therefore necessary and currently correct
- this is a data sync / coverage mismatch, not a ranking bug

### History sufficiency
Across the 96 valid NDX members:
- scored symbols: `96`
- minimum `bars_available`: `634`
- maximum `bars_available`: `770`

Interpretation:
- all valid symbols had enough history for `ROC60`
- no symbol was excluded for insufficient warmup in this sample

### Top10 ROC60 for 2026-03-25
| Rank | Symbol | ROC60 | Close | Bars |
|---:|:---|---:|---:|---:|
| 1 | WDC | 0.6312658367 | 296.14 | 764 |
| 2 | STX | 0.4437146251 | 413.22 | 770 |
| 3 | ARM | 0.4244128049 | 157.07 | 634 |
| 4 | AMAT | 0.4102329133 | 369.34 | 764 |
| 5 | BKR | 0.3838674033 | 62.62 | 762 |
| 6 | MU | 0.3416552547 | 382.09 | 764 |
| 7 | FANG | 0.3397580480 | 196.02 | 764 |
| 8 | LRCX | 0.3110012916 | 233.45 | 764 |
| 9 | INTC | 0.3033149171 | 47.18 | 764 |
| 10 | ASML | 0.2993614542 | 1393.89 | 764 |

## Determinism checks
- ranking tie-break remains:
  - score descending
  - symbol ascending
- `select_top_n(...)` adds deterministic `rank`
- no NaN scores in final ranking set
- no zero/negative close values in final ranking set

## Current limitations
- `current_members` only
- validity remains `INDICATIVE_ONLY`
- no PIT membership support
- no monthly rebalance logic yet
- no multi-horizon score yet
- no regime filter yet
- no order intent generation yet

## Conclusion
The bottom-up slice is now working for real data:
- universe membership is consumed from `marketdata-stream`
- daily bars are intersected locally
- `ROC60` is computed correctly on the market date boundary
- deterministic Top10 output is available in CLI and Spyder

The next clean step is:
1. persist the ranking snapshot as a strategy debug artifact
2. compare `ROC20`, `ROC60`, `ROC120`
3. decide whether to keep simple ROC or move to the planned multi-horizon score
