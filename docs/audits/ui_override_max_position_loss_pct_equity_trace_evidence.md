# UI Override Trace Evidence — max_position_loss_pct_equity

## Executive Summary
- UI **loads** `max_position_loss_pct_equity` from YAML as **tunable=0.0 (float)**.
- During Save, **UI raw value varies** (`None`, `0.3` float, `0` int), but **no overrides are persisted**.
- `_compute_overrides` sees **original=0 (int)**, so when UI sends `0.3` it still records **0 overrides** → no YAML update.
- This explains why UI shows “Saved” but YAML remains `0.0`.

## Evidence (logs/dashboard.log)

### Loaded defaults
```
2026-02-02 08:34:13 ... ui_loaded_default key=max_position_loss_pct_equity section=tunable val=0.0 type=float strategy_id=insidebar_intraday version=1.0.1
```

### Save triggers + raw values
```
2026-02-02 08:34:22 ... ui_trigger [{'prop_id': 'ssot:save-version.n_clicks', 'value': 1}]
2026-02-02 08:34:22 ... ui_param_raw key=max_position_loss_pct_equity value_repr=None value_type=NoneType
2026-02-02 08:34:22 ... ui_param_orig key=max_position_loss_pct_equity orig=0 orig_type=int
2026-02-02 08:34:22 ... ui_config_updated_inplace ... core_overrides=0 tunable_overrides=0

2026-02-02 08:34:27 ... ui_trigger [{'prop_id': 'ssot:save-version.n_clicks', 'value': 2}]
2026-02-02 08:34:27 ... ui_param_raw key=max_position_loss_pct_equity value_repr=0.3 value_type=float
2026-02-02 08:34:27 ... ui_param_orig key=max_position_loss_pct_equity orig=0 orig_type=int
2026-02-02 08:34:27 ... ui_config_updated_inplace ... core_overrides=0 tunable_overrides=0

2026-02-02 08:34:29 ... ui_trigger [{'prop_id': 'ssot:save-version.n_clicks', 'value': 3}]
2026-02-02 08:34:29 ... ui_param_raw key=max_position_loss_pct_equity value_repr=0 value_type=int
2026-02-02 08:34:29 ... ui_param_orig key=max_position_loss_pct_equity orig=0 orig_type=int
2026-02-02 08:34:29 ... ui_config_updated_inplace ... core_overrides=0 tunable_overrides=0
```

### Additional attempts (same pattern)
```
2026-02-02 08:18:26 ... ui_param_raw ... value_repr=0.3 value_type=float
2026-02-02 08:18:26 ... ui_param_orig ... orig=0 orig_type=int
2026-02-02 08:18:34 ... ui_param_raw ... value_repr=None value_type=NoneType
```

## Root Cause (evidence-based)
- Loader shows YAML default is **float 0.0**, but `_compute_overrides` sees **orig=0 (int)**.
- When UI sends `0.3`, overrides are still **not recorded** (`core_overrides=0 tunable_overrides=0`).
- This implies a **type/compare mismatch** or a **value normalization to int 0** happens **between defaults load and overrides**.

## Likely failure points (needs follow-up inspection)
1) `loaded_defaults` stored in dcc.Store may be **coerced/serialized to int**.
2) `edited_values` can arrive as `None` for the same field (seen in logs).

## Next forensic checks (no fix yet)
- Inspect how `loaded_defaults` is serialized into the store (JSON serialization path) and whether floats become ints.
- Inspect `edited_values` for missing/None and input component type.

