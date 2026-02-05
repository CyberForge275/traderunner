# InsideBar Entry Fill Stop/Cross Fix

Date: 2026-02-05
Branch: fix/insidebar-entry-fill-stop-cross
Rollback tag: insideBar_pre_entry_fill_fix

## Problem (repro)
Run: `260205_155815_HOOD_IB_mbhl_ib_300d`
Template: `ib_HOOD_20250530_135500`

- Intent entry_price: **63.42** (mother_low)
- Fill entry_price: **63.05** (bar close)
- Expected: stop/cross fill at trigger (63.42) or open on gap

## Before (behavior)
Entry fills were always set to bar close at `signal_ts`.

Code location:
- `src/axiom_bt/pipeline/fill_model.py` (`generate_fills`, entry fill uses `bar["close"]`)

## After (rule)
Stop-entry fill uses trigger level or open on gap for insidebar intents:

SELL (trigger = mother_low):
- if open <= trigger → fill = open (gap)
- else if high >= trigger >= low → fill = trigger

BUY (trigger = mother_high):
- if open >= trigger → fill = open (gap)
- else if high >= trigger >= low → fill = trigger

If no cross (unexpected), fallback to close with reason logged.

## Implementation notes
- Scope: only insidebar intents (`strategy_id == "insidebar_intraday"`).
- No change to signal generation, SL/TP, or session logic.
- Logging:
  `actions: entry_fill_stop_cross side=... trig=... open=... high=... low=... fill=... reason=... template_id=... signal_ts=...`

## Tests
New unit tests:
- `tests/pipeline/test_fill_model_entry_stop_cross.py`
  - SELL crossing → fill = trigger
  - SELL gap → fill = open
  - BUY crossing → fill = trigger
  - BUY gap → fill = open

Commands:
```
PYTHONPATH=src:. pytest -q tests/pipeline/test_fill_model_entry_stop_cross.py
```

## Rollback
```
git checkout main
git reset --hard insideBar_pre_entry_fill_fix
```
