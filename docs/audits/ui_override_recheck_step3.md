# Step 3 — YAML write path & payload (read-only)

## Override diff location
File: `trading_dashboard/callbacks/ssot_config_viewer_callback.py`

```
$(cat /tmp/ssot_compute_overrides.txt)
```

Key lines:
- new_value computed for float: `float(value) if value else 0.0`
- override only added if `new_value != original`

## Store → Manager → Repository write path
File: `trading_dashboard/config_store/strategy_config_store.py`

```
$(cat /tmp/strategy_config_store.txt)
```

File: `src/strategies/config/repository.py`

```
$(cat /tmp/repository_write.txt)
```

## Write mechanics
- Overrides are applied by Manager (not shown here).
- Repository writes YAML via `yaml.dump(content, ...)` with atomic tmp+rename.
- If `new_value` becomes `0.0`, it is persisted as an override into YAML.
