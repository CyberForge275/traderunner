# Forensic Report — UI override `max_position_loss_pct_equity` becomes `0.0` when UI value is "0,03"

## Observed Symptom
- YAML contains: `max_position_loss_pct_equity: 0.0`
- UI value entered: `0,03`
- UI shows error: `inside_bar v1.0.1 invalid max_position_loss_pct_equity: 0.0`

## Repro Steps (Read-only)
1) Locate conversion logic in UI callback.
2) Simulate conversion with `value="0,03"`.
3) Trace write path to YAML.

## Evidence — Code Locations & Lines
### A) UI conversion (where string becomes float or 0.0)
File: `trading_dashboard/callbacks/ssot_config_viewer_callback.py`

```text
Lines 445–450 (see nl -ba)
445  if isinstance(original, bool):
446      new_value = (value == ["true"]) if isinstance(value, list) else bool(value)
447  elif isinstance(original, int):
448      new_value = int(value) if value else 0
449  elif isinstance(original, float):
450      new_value = float(value) if value else 0.0
```

**Implication:**
- If `value` is `"0,03"`, `float("0,03")` raises `ValueError` (comma not parsed).
- If `value` is `""` or `None`, new_value is forced to `0.0`.

### B) YAML write path (where overrides persist)
Call chain:
- UI callback: `save_config()` → `_compute_overrides()`
- Store: `StrategyConfigStore.save_new_version(...)` or `update_existing_version(...)`
- Manager: `InsideBarConfigManager.add_version(...)` (via manager_base)
- Repository: `StrategyConfigRepository.write_strategy_file(...)`

File: `src/strategies/config/repository.py`

```text
write_strategy_file()
- dumps `content` to YAML using yaml.dump()
```

## Evidence — Repro Simulation (no UI)
Python snippet (in repo root):

```python
original=0.01 value='0,03' -> EXC ValueError: could not convert string to float: '0,03'
original=0.01 value='0.03' -> new_value=0.03 type=float
original=0.01 value='' -> new_value=0.0 type=float
original=0.01 value=None -> new_value=0.0 type=float
```

**Conclusion from simulation:**
- `"0,03"` crashes in `float()` parsing.
- Empty or missing values are coerced to `0.0`.

## Root Cause (High Confidence)
The UI uses `float(value)` for float fields in `_compute_overrides()`, which **does not accept comma decimals** (`"0,03"`). If the field is empty or value is missing, it **coerces to `0.0`**, which then gets saved as an override into YAML.

## Fix Recommendation (NOT IMPLEMENTED)
### Option 1 — Locale-tolerant float parsing
- Before `float(value)`, normalize string:
  - `value = value.replace(",", ".")` if it’s a str.

### Option 2 — Treat empty input as “no override”
- If `value` is `""` or `None`, skip override:
  - `return original` or `continue`.

### Option 3 — Explicit validation in UI
- If `value` contains comma, parse and store as float, else show UI error.

## GO/NO-GO
Evidence is complete. Ready for minimal fix. GO FIX?
