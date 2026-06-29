# Perlentaucher — Current Status and Learnings

## Scope
This document captures the current project state for `perlentaucher_daily_scan` and the main learnings from the recent sweet-spot and high-impulse breakout research.

It is intentionally limited to the Perlentaucher strategy area.

## Current Strategy State

### 1. Main Perlentaucher strategy path
The current Perlentaucher strategy exists as a strategy-local implementation with:
- strategy registration and config wiring already in place
- a daily prefilter for candidate reduction
- slope-based feature computation
- sweet-spot reference extraction and aggregation
- candidate matching against the sweet-spot reference set
- signal enrichment for actionable long rows
- strategy-local intent generation for the current MVP order semantics

The existing Perlentaucher path is still best described as:
- a scan/signal strategy with partial backtestability
- based on sweet-spot slope similarity
- not yet the final production-grade execution strategy

### 2. Independent AXTI-style impulse research path
A separate, independent research branch now exists inside Perlentaucher.

This path does **not** modify the current sweet-spot logic. It is isolated in:
- `impulse_features.py`
- `impulse_trigger.py`
- `impulse_inspection.py`
- `tools/run_impulse_trigger_spyder.py`

This branch was introduced to test whether a strict high-impulse breakout model should remain within Perlentaucher research or become a separate strategy.

## Implemented Independent Impulse Logic

### Feature layer
The independent impulse feature layer computes:
- trimmed linear regression slope on the pre-window price path
- trimmed linear regression slope on the pre-window volume path
- price ratio from day `T-1` to breakout day `T`
- volume ratio from day `T-1` to breakout day `T`
- price ratio from day `T-1` to confirmation day `T+1`
- volume ratio from day `T-1` to confirmation day `T+1`

Additional structural fields were added after qualitative review:
- `breakout_green`
- `confirm_close_vs_breakout_close`
- `confirm_vol_vs_breakout_vol`
- `pre_max_drawdown`
- `pre_gap_down_count`

### Decision layer
The independent trigger layer now rejects setups if one of the following holds:
- precondition slope fails
- pre-window path is too rough
- breakout bar is red
- breakout thresholds are too weak
- confirmation data is missing
- confirmation close retention is too weak
- confirmation thresholds are too weak

Current explicit reject reasons include:
- `PRECONDITION_FAILED`
- `PREWINDOW_PATH_REJECTED`
- `BREAKOUT_THRESHOLD_FAILED`
- `BREAKOUT_BAR_REJECTED`
- `CONFIRMATION_DATA_MISSING`
- `CONFIRMATION_CLOSE_REJECTED`
- `CONFIRMATION_THRESHOLD_FAILED`
- `IMPULSE_CONFIRMED`

## Key Learning: Perlentaucher vs High-Impulse Breakout
The current evidence shows that the AXTI-style setup is materially different from the main Perlentaucher sweet-spot strategy.

### Perlentaucher core character
Perlentaucher currently centers on:
- slope-shape similarity
- aggregated sweet-spot references
- multi-symbol profile matching

### High-impulse breakout character
The independent AXTI-style path centers on:
- explicit cold-phase precondition
- explicit breakout-day price/volume jump
- explicit next-day confirmation
- structural rejection of weak or unstable patterns

### Conclusion
This suggests:
- research can remain inside Perlentaucher for now
- but a production implementation would likely deserve a separate strategy if the edge remains valid

## Sweet-Spot Learnings

### Current sweet-spot reference handling
The strategy already supports:
- strategy-local sweet-spot config
- strategy-local sweet-spot cache
- cache invalidation when the configured symbol/date set changes

### Important cache rule
The cache must match the configured reference set exactly.
If the configured sweet-spot symbols or dates change, the cached reference artifacts are treated as stale and must be recalculated.

## High-Impulse Research Learnings

### AXTI baseline
AXTI remains the anchor example for the strict impulse model.
Important practical note:
- AXTI's cold phase is **below** `$3`
- therefore a literal `3–9 USD` cold-phase filter would exclude AXTI itself

### Cold-phase compatibility filter
For the broader scan, the practical AXTI-compatible reduction was:
- cold-phase price band: `2–9 USD`
- cold-phase mean volume: `100k–1.5M`
- cold-phase median volume: `80k–1.2M`

This reduced the 90-day US full-universe scan to:
- `588` unique symbols
- `27,978` evaluated symbol-days

### Strict 90-day scan result
On the reduced universe with strict AXTI thresholds and the newer structural reject gates:
- `90` analysis session days
- `19` weeks in window
- `6` true pass symbol-days
- `6` weeks with at least one true pass
- `13` weeks without a true pass

This means:
- the setup is rare, but not empty
- frequency is low enough that a dedicated strategy would have low trade count

## Qualitative Review Learnings
The manual review of candidates led to additional rejection logic.

### Rejected characteristics now encoded
The following were identified as meaningful weak-pattern signs:
- red breakout bar
- weak confirmation close relative to breakout close
- too rough pre-window path before breakout

### Observed post-entry warning patterns
From comparing biggest simulation winners vs biggest simulation losers among near-misses, the most useful bearish clues were:
- red entry bar
- first two hold bars both red
- repeated red bars early in the hold period
- deep early drawdown after entry

Bullish continuation tended to show:
- green entry bar
- no two-red-bars start after entry
- orderly continuation even with lower follow-up volume
- shallower early drawdown

These observations are not yet part of the current independent trigger contract, but they are good candidates for future validation.

## Simple Simulation Learnings
A simple research simulation was applied to the strict impulse passes and weekly closest misses.

### Simulation assumptions
- signal day = `T`
- buy = `T+2` open
- hold = `5` trading bars
- sell = close on the 5th bar in position
- capital = `$1000` per signal

### Result on strict true passes
The strict pass set was only slightly positive in the small sample.
This is not yet enough evidence for a robust tradable edge.

### Result on weekly closest misses
The closest misses were mixed:
- some performed strongly
- some failed badly

This suggests the current gates are directionally useful, but the post-entry behavior still needs deeper testing before strategy promotion.

## Extended Holding Learnings

### Relaxed research baseline
For the broader holding analysis, the isolated impulse model was tested with a relaxed research baseline:
- cold-phase price band: `2–9 USD`
- cold-phase mean volume: `100k–1.5M`
- cold-phase median volume: `80k–1.2M`
- relaxed structural gates
- entry at `T+2` open

This baseline improved over the stricter version and produced enough signals for a larger holding-period comparison.

### Fixed holding windows
Using the relaxed baseline and `$1000` per signal, the fixed-window results were:

- `10` bars:
  - total PnL: `-258.77`
  - average return: `-1.00%`
  - median return: `-0.69%`
  - win rate: `42.31%`

- `20` bars:
  - total PnL: `+3116.35`
  - average return: `+11.99%`
  - median return: `+0.47%`
  - win rate: `57.69%`

- `35` bars:
  - total PnL: `+4023.16`
  - average return: `+16.76%`
  - median return: `+1.01%`
  - win rate: `54.17%`

- `50` bars:
  - total PnL: `+6650.80`
  - average return: `+28.92%`
  - median return: `+3.71%`
  - win rate: `56.52%`

### Important data-quality correction for \"hold to latest\"
The first \"hold to latest available close\" result was invalid.

Root cause:
- `ATXS` contained a terminal zero-volume row:
  - `2026-03-20`
  - `open=high=low=close=5298.00`
  - `volume=0`
- that single row created a fake PnL contribution of about `+444,210`

Additional zero-volume terminal bars were also found in:
- `CVAC`
- `QIPT`
- `THTX`

### Corrected rule for terminal exits
For exploratory \"hold to latest\" analysis, zero-volume terminal bars must be treated as invalid exits.
The correct fallback is:
- exit on the last tradable bar only

### Corrected \"hold to latest\" conclusion
After removing the bad zero-volume terminal exits and replacing them with each symbol's last tradable bar:
- the total PnL drops from an invalid `+450,661.58`
- to a plausible level of about `+6508.64`

This means:
- the huge original result was a data artifact
- the corrected result is still positive
- but it is no longer absurdly dominated by one broken row

### Practical interpretation
The current evidence suggests:
- short holds (`5–10` bars) are weak
- medium holds (`20–50` bars) are materially stronger
- `50` bars currently looks like the most promising simple baseline
- \"hold to latest\" is useful only as secondary exploratory analysis, never as a primary performance metric

### Corrected tradable-only comparison
Using the relaxed baseline, entry at `T+2` open, and excluding zero-volume exit bars:

- `50` bars:
  - simulated: `24`
  - total PnL: `+6715.51`
  - average return: `+27.98%`
  - median return: `+4.07%`
  - win rate: `58.33%`

- hold to latest tradable bar:
  - simulated: `31`
  - total PnL: `+6508.64`
  - average return: `+21.00%`
  - median return: `+3.00%`
  - win rate: `61.29%`

This means:
- `50` bars and \"hold to latest tradable\" are now in the same realistic order of magnitude
- the invalid `+450k` artifact is gone
- `50` bars remains a valid fixed-horizon baseline
- \"hold to latest tradable\" can stay as a secondary exploratory comparison because it still captures occasional high flyers without using invalid terminal rows

### Stop-loss overlays on the latest-tradable path
To test basic downside control without adding a take-profit cap, the following stop overlays were checked on the \"hold to latest tradable\" path:

- `20%` stop:
  - total PnL: `+3109.72`
  - average return: `+10.03%`
  - median return: `-11.89%`
  - win rate: `41.94%`

- `30%` stop:
  - total PnL: `+2778.59`
  - average return: `+8.96%`
  - median return: `-6.39%`
  - win rate: `45.16%`

- `40%` stop:
  - total PnL: `+4087.42`
  - average return: `+13.19%`
  - median return: `+1.06%`
  - win rate: `54.84%`

Current reading:
- the tighter `20%` and `30%` stops cut too many eventual winners
- the `40%` stop is less destructive, but still underperforms the no-stop latest-tradable path
- for this specific research sample, the setup appears to need room to run more than it needs tight stop protection

### Trailing-stop overlays on the latest-tradable path
The next test replaced the fixed stop-loss idea with a trailing stop on the same \"hold to latest tradable\" path.

The best result in this sample came from a `30%` trailing stop:

- no-stop hold to latest tradable:
  - total PnL: `+6508.64`
  - average return: `+21.00%`
  - median return: `+3.00%`
  - win rate: `61.29%`

- `30%` trailing stop:
  - total PnL: `+10242.01`
  - average return: `+33.04%`
  - median return: `+0.43%`
  - win rate: `51.61%`

This means:
- the `30%` trailing stop improves total PnL materially
- but it does not improve the trade distribution evenly
- the gain comes mainly from preventing a subset of severe give-backs

### Where the `30%` trailing stop helped most
The clearest improvements versus the no-stop latest-tradable path were:

- `RGTIW`
  - latest-tradable PnL: `+312.79`
  - `30%` trail PnL: `+4045.61`
  - delta: `+3732.82`

- `TERN`
  - latest-tradable PnL: `-965.03`
  - `30%` trail PnL: `+968.65`
  - delta: `+1933.68`

- `PTIX`
  - latest-tradable PnL: `-805.42`
  - `30%` trail PnL: `-112.07`
  - delta: `+693.35`

- `NEOV`
  - latest-tradable PnL: `-434.69`
  - `30%` trail PnL: `+68.74`
  - delta: `+503.43`

- `ORGO`
  - latest-tradable PnL: `-633.69`
  - `30%` trail PnL: `-234.00`
  - delta: `+399.69`

These are the strongest examples of the \"moonshot then give-back\" failure mode.

### Where the `30%` trailing stop hurt most
The clearest regressions versus the no-stop latest-tradable path were:

- `SOGP`
  - latest-tradable PnL: `+1796.30`
  - `30%` trail PnL: `-265.00`
  - delta: `-2061.30`

- `OMER`
  - latest-tradable PnL: `+470.34`
  - `30%` trail PnL: `-296.36`
  - delta: `-766.70`

- `CORZW`
  - latest-tradable PnL: `+548.14`
  - `30%` trail PnL: `-211.25`
  - delta: `-759.39`

- `ATOM`
  - latest-tradable PnL: `+531.88`
  - `30%` trail PnL: `-38.62`
  - delta: `-570.49`

- `ACRS`
  - latest-tradable PnL: `+105.38`
  - `30%` trail PnL: `-240.36`
  - delta: `-345.74`

This shows the trade-off clearly:
- the trailing stop protects against deep collapses
- but it also cuts off some names that later recover or continue trending

### Current interpretation of the trailing-stop result
On this sample:
- `12` signals improved under the `30%` trail
- `6` signals got worse
- `13` were unchanged

So the trailing stop is not universally better.
It is specifically valuable where large interim gains are followed by severe reversals.

## Current Constraints
The current working rules for this project branch have been:
- changes only inside `src/strategies/perlentaucher_daily_scan/**`
- no changes outside Perlentaucher without explicit approval
- config changes only with explicit approval
- no external interface changes
- marketdata-stream integration remains unchanged

These constraints were preserved during the impulse research work.

## Tests Status
Perlentaucher-local tests are currently green.

Recent validated suite state:
- `55 passed`
- strategy-local only

The independent impulse path has dedicated tests for:
- feature construction
- trigger evaluation
- combined inspection behavior

## Recommended Next Steps

### If continuing research inside Perlentaucher
The next sensible steps are:
1. run broader batched scans on the reduced cold-phase universe
2. validate the post-entry candle pattern hypotheses on a larger sample
3. compare strict passes vs closest misses over multiple holding rules

### If moving toward a separate strategy
A separate high-impulse breakout strategy becomes justified if:
- the strict setup keeps recurring with acceptable frequency
- the edge holds under larger out-of-sample simulation
- the post-entry behavior can be formalized into a stable entry/exit model

### Practical decision boundary
If the high-impulse model remains:
- sparse
- explicit-ratio driven
- structurally distinct from sweet-spot matching

then it should not be forced back into the main Perlentaucher strategy.
It should become its own strategy family.

## Current Bottom Line
- The main Perlentaucher sweet-spot strategy path exists and is usable as a research/backtest scaffold.
- The AXTI-style breakout work is now implemented as a separate independent research block inside Perlentaucher.
- The stricter impulse gating reflects recent manual review feedback.
- The strict breakout setup is rare but recurring.
- The best current research direction is no longer stricter filtering, but better execution semantics and medium-term holding analysis.
- It is still unresolved whether this should remain a research branch or become a standalone strategy.


## Cleaned Baseline After Invalid-Symbol Exclusions

The 600-session first-trigger research set was cleaned to remove symbols that should not remain in the common-stock baseline basket:
- `ITI`
  - invalid source identity / stitched series issue
- `TERN`
  - invalid tail regime in local data, inconsistent with Yahoo Finance
- `RGTIW`
  - warrant, not common stock

The saved export was updated in:
- `src/strategies/perlentaucher_daily_scan/docs/research/impulse_600_session_first_trigger_candidates_relaxed_baseline.csv`
- `src/strategies/perlentaucher_daily_scan/docs/research/impulse_600_session_first_trigger_candidates_relaxed_baseline.meta.json`
- `src/strategies/perlentaucher_daily_scan/docs/research/impulse_600_session_first_trigger_candidates_relaxed_baseline.md`

`INOD` and `VTYX` remain in the basket, but only under strict zero-volume filtering.

### Cleaned Candidate Counts
- first-trigger candidates: `156`
- final-trigger candidates: `65`

### Cleaned First-Trigger Results
Fixed notional: `$1000` per trade
Entry: next trading day open after first trigger
Zero-volume bars ignored

#### 50-day hold
- baseline, no stop
  - trades: `135`
  - total PnL: `+11111.75`
  - avg return: `+8.23%`
  - median return: `-1.22%`
  - win rate: `45.93%`

- fixed `50%` stop from entry
  - trades: `135`
  - total PnL: `+12345.51`
  - avg return: `+9.14%`
  - median return: `-1.22%`
  - win rate: `45.93%`

#### 60-day hold
- baseline, no stop
  - trades: `124`
  - total PnL: `-47.23`
  - avg return: `-0.04%`
  - median return: `-3.85%`
  - win rate: `43.55%`

- fixed `50%` stop from entry
  - trades: `124`
  - total PnL: `+1659.59`
  - avg return: `+1.34%`
  - median return: `-3.85%`
  - win rate: `43.55%`

#### 70-day hold
- baseline, no stop
  - trades: `121`
  - total PnL: `-1643.61`
  - avg return: `-1.36%`
  - median return: `-11.95%`
  - win rate: `39.67%`

- fixed `50%` stop from entry
  - trades: `121`
  - total PnL: `+281.15`
  - avg return: `+0.23%`
  - median return: `-11.95%`
  - win rate: `39.67%`

### Updated Conclusion
After removing the contaminated names, the long-hold thesis weakens materially.

Current clean ranking:
1. `50`-day hold with fixed `50%` stop
2. `50`-day hold without stop
3. `60`-day hold with fixed `50%` stop
4. `60`-day hold without stop (roughly flat)
5. `70`-day hold with fixed `50%` stop (roughly flat)
6. `70`-day hold without stop (negative)

Practical baseline going forward:
- primary baseline:
  - `50`-day hold, no stop
- main comparison:
  - `50`-day hold with fixed `50%` stop

The longer-hold variants are no longer supported once the obvious data-quality contaminants are removed.


## Normalized 15k Portfolio Comparison

The cleaned first-trigger set was also compared on a normalized portfolio basis with the same `15,000` starting capital.

Common assumptions:
- holding period: `50` trading days
- zero-volume bars ignored
- cleaned set excludes:
  - `ITI`
  - `TERN`
  - `RGTIW`

### Comparison Table

| Variant | Start Capital | Sizing | Margin Rule | Stop | End Equity | Profit | Return | Max DD | Max Open |
|---|---:|---|---|---|---:|---:|---:|---:|---:|
| Fixed baseline | `15,000` | fixed `1,000` per trade | none | none | `26,111.75` | `+11,111.75` | `+74.08%` | `-49.62%` | `22` |
| Fixed baseline + stop | `15,000` | fixed `1,000` per trade | none | fixed `50%` | `27,345.51` | `+12,345.51` | `+82.30%` | `-46.00%` | `22` |
| Adjusted | `15,000` | `equity / 15` | margin only above `15k`, profits only, reduce new entries if needed, no new entries below `15k` | none | `25,644.48` | `+10,644.48` | `+70.96%` | `-41.47%` | `21` |
| Adjusted + stop | `15,000` | `equity / 15` | margin only above `15k`, profits only, reduce new entries if needed, no new entries below `15k` | fixed `50%` | `27,712.41` | `+12,712.41` | `+84.75%` | `-39.98%` | `21` |

### Interpretation
- The fixed `50%` stop improves both portfolio models.
- The adjusted portfolio policy outperforms the fixed-notional baseline when the stop is included.
- The adjusted policy also reduces drawdown versus the fixed-notional baseline.
- Without the stop, the adjusted policy reduces drawdown but also slightly reduces total return.

### Current Portfolio Recommendation
Working research baseline for the cleaned set:
- start capital: `15,000`
- target position size: `equity / 15`
- no new entries when `equity <= 15,000`
- margin allowed only above `15,000`
- margin unlocked only against profits
- reduce new entry size when margin capacity is tight
- fixed `50%` stop from entry
- `50`-day holding period

This is the cleanest current portfolio policy on the cleaned dataset.
