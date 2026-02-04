# InsideBar Body Rule Change Audit (2026-02-04 15:13)

## Snapshot
- Repo: /home/mirko/data/workspace/droid/traderunner
- HEAD (pre-change): 1f9cc7dc78452664546a826ea05d582a72a55e08
- Backup branch: backup/insidebar_pre_body_rule_20260204_1513
- Checkpoint tag: checkpoint/insidebar_pre_body_rule_20260204_1513

## Old vs New Rule (Boolean Form)
**Old (range-based, inclusive/strict):**
- Inclusive: `ib_high <= mother_high AND ib_low >= mother_low`
- Strict: `ib_high < mother_high AND ib_low > mother_low`

**New (mother body-based):**
Let:
- `body_low = min(mother_open, mother_close)`
- `body_high = max(mother_open, mother_close)`

- Inclusive: `ib_high <= body_high AND body_low <= ib_close <= body_high`
- Strict: `ib_high < body_high AND body_low < ib_close < body_high`

**Notes:**
- Only `ib_high` and `ib_close` are used for inside determination; `ib_low` is not part of the rule.
- Mother high/low still define breakout levels; only inside detection changes.

## Columns Used
- Mother: `prev_open`, `prev_close`, `prev_high`, `prev_low`
- Inside: `high`, `close`

## Example (numeric)
Mother bar: open=100, close=103 → body_low=100, body_high=103
Inside bar:
- high=102.5, close=101.5 → inside=True (inclusive)
- high=103.2, close=101.5 → inside=False (high above body_high)
- high=102.5, close=99.5 → inside=False (close below body_low)

## Code Locations
- Inside-bar detection: `src/strategies/inside_bar/core.py:210-244` (body-based mask)
- Session IB gate: `src/strategies/inside_bar/core.py:443-456` (body-based mask for arming)

## Impact (Expected)
- Only inside-bar classification changes.
- No change to ATR, sizing, session logic, or SL/TP computation.
- No lookahead introduced (uses previous bar only).

## Tests
- Command: `PYTHONPATH=src:. pytest -q src/strategies/inside_bar/tests/test_core.py`
- Result: 21 passed

## Invariants
- Breakout levels still use mother high/low (unchanged).
- Intent/fill/trade data untouched.
- No new dependencies added.
