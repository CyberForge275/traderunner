# InsideBar Mother-Size Filter — Doc Alignment Report

## Doc Evidence (quoted, ≤25 words each)

1) `src/strategies/inside_bar/docs/INSIDE_BAR_SSOT.md:56`
> "mother_range >= min_mother_bar_size * ATR"

2) `src/strategies/inside_bar/docs/UNIFIED_STRATEGY_PLAN.md:186-190`
> "Minimum mother bar size filter … prev_range >= (min_mother_bar_size * df['atr'])"

3) `src/strategies/inside_bar/strategy.py:77-81`
> "Minimum size of mother bar as multiple of ATR"

## Doc Interpretation
- **Reference measure:** ATR (True Range SMA per plan).  
- **Index specificity:** **Ambiguous** — docs do not explicitly state whether ATR is from mother bar (i-1) or inside bar (i).

## Decision (Minimal-Risk Interpretation)
- Use **ATR of the mother bar (i-1)** for the mother size filter.
- Rationale: filter describes **mother bar quality**; using mother ATR is the most literal and stable mapping.

## Code Change Summary

### Old behavior (pre-change)
- `detect_inside_bars`: size_ok used **current row ATR** (inside-bar ATR).
- `generate_signals`: mother size check used **current row ATR**.

### New behavior (post-change)
- `detect_inside_bars`: size_ok uses **ATR shifted by 1** (mother bar ATR).
- `generate_signals`: mother size check uses `prev['atr']` (mother ATR).
- If ATR missing or <=0 and `min_mother_bar_size > 0` → reject (conservative).

## Code Locations
- `src/strategies/inside_bar/core.py`:
  - `detect_inside_bars`: mother size filter block (around lines ~230–245)
  - `generate_signals`: mother size check block (around lines ~430–450)

## Tests Added/Updated
- `src/strategies/inside_bar/tests/test_core.py`
  - `test_mother_size_filter_disabled_when_zero`
  - `test_mother_size_filter_uses_mother_atr`
  - `test_mother_size_filter_rejects_when_atr_missing`

## Test Result (local)
- `pytest -q src/strategies/inside_bar/tests/test_core.py`

## Risk / Impact
- **Behavioral change** in mother-size gating when ATR differs between mother and inside bars.
- Change is deterministic and doc-aligned; no other strategy logic touched.
