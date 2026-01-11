# Strategy Config Manager (Schritt 0) - Technical Report

## Summary
Successfully implemented the bottom-up Foundation for Strategy Config SSOT, focusing on `InsideBar`. This step provides a read-only, validation-heavy manager for versioned YAML configurations.

## Files Created/Modified
- `configs/strategies/inside_bar.yaml`: SSOT YAML storage.
- `src/strategies/config/repository.py`: YAML reading and path resolution.
- `src/strategies/config/manager_base.py`: Abstract loading and common validation.
- `src/strategies/config/specs/inside_bar_spec.py`: Strategy-specific schema and type rules.
- `src/strategies/config/managers/inside_bar_manager.py`: Concrete manager for InsideBar.
- `tests/test_strategy_config_manager_inside_bar.py`: 8 hermetic unit tests.

## Schritt 1.1: strategy_id Alignment & Generic Registry
Successfully refactored the system to use `strategy_id` as the primary lookup key, removing all hardcoded "if/else" mappings in the Store.

### Implementation Details
- **YAML Schema**: Now includes `strategy_id` at the top level and versions nested under `versions:`.
- **Manager Registry**: Introduced `src/strategies/config/registry.py` for generic manager lookup.
- **Lazy Repository**: `StrategyConfigRepository` now evaluates `STRATEGY_CONFIG_ROOT` lazily, allowing environment overrides during test execution after module imports.
- **ID Alignment**: Confirmed `insidebar_intraday` as the standard ID across UI and YAML.

### Files Added/Modified
- `src/strategies/config/registry.py`: [NEW] Singleton registry.
- `src/strategies/config/managers/inside_bar_manager.py`: [MOD] Registers itself as `insidebar_intraday`.
- `trading_dashboard/config_store/strategy_config_store.py`: [MOD] Generic registry lookup.
- `configs/strategies/inside_bar.yaml`: [MOD] New schema format.

### Verification
- **Total Tests**: 14 (11 Manager + 3 Store Contract).
- **Command**: `pytest -q tests/test_strategy_config_store_ui_contract.py tests/test_strategy_config_manager_inside_bar.py` (ALL PASS)
