# UI→YAML Re-Validation — `max_position_loss_pct_equity` with value "0,03"

## Executive Summary
- UI conversion uses `float(value)` for float fields. Comma decimals ("0,03") raise `ValueError`.
- If UI passes empty/None, code coerces to `0.0` and writes override.
- YAML write path persists the override through Manager → Repository.

## Evidence Table
| Step | Evidence | Result |
|------|----------|--------|
| A | `_compute_overrides` uses `float(value) if value else 0.0` | Comma decimals fail; empty -> 0.0 |
| B | Repro script: value="0,03" | `ValueError: could not convert string to float` |
| C | Repro script: value="" or None | override set to `0.0` |
| D | YAML write path | `write_strategy_file()` persists override into YAML |

## Evidence (line refs)
- Conversion logic: `trading_dashboard/callbacks/ssot_config_viewer_callback.py` lines 447–450
- Override inclusion: lines 469–474
- YAML write: `src/strategies/config/repository.py` lines 60–100

## Root Cause Decision
**Primary cause:** UI string "0,03" is not parsed by `float()` and raises `ValueError`.
**Secondary cause:** empty/None UI values are coerced to `0.0`, which then becomes a YAML override.

## Fix Candidates (no implementation)
1) Pre-parse float fields: if `isinstance(value, str)`, replace comma with dot before `float()`.
2) Treat empty/None as “no override” (skip instead of `0.0`).
3) If value is list (unexpected), either reject with explicit error or handle first item.

## Artifacts
- `docs/audits/ui_override_recheck_step1.md`
- `docs/audits/ui_override_recheck_step2.md`
- `docs/audits/ui_override_recheck_step3.md`
- `docs/audits/repro_ui_override_comma03.py`
- `docs/audits/repro_ui_override_comma03.out`

## GO/NO-GO
Evidence is sufficient. **GO FIX?**
