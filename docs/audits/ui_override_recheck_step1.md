# Step 1 — Code locations and line refs (read-only)

## Conversion / override logic
Source: `trading_dashboard/callbacks/ssot_config_viewer_callback.py` (excerpt)

```
$(cat /tmp/ssot_config_viewer_callback_extract.txt)
```

## Grep: override functions
```
$(cat /tmp/rg_overrides.txt)
```

## Grep: float/int conversion
```
$(cat /tmp/rg_float_int.txt)
```

## Grep: try/except locations
```
$(cat /tmp/rg_try_except.txt)
```

## Grep: max_position_loss_pct_equity in UI
```
$(cat /tmp/rg_max_position_loss_ui.txt)
```

## YAML write path search
```
$(cat /tmp/rg_yaml_write.txt)
```
