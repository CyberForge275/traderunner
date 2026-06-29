# ndx_momentum_rotation (Skeleton)

This package is a compile-safe skeleton for a cross-sectional monthly rotation strategy.

## Current status
- Plugin + schema + config contracts are present.
- Trading logic is intentionally incomplete.
- `extend_signal_frame` fails fast when bars are not multi-symbol.

## Risk guards implemented
- Cross-sectional guard (`symbol` column + >=2 unique symbols required)
- Lookahead guard (`signal_ts < exec_ts` enforced)
- Survivorship validity class (`current_members` -> `INDICATIVE_ONLY`)
- Strict config validation for enums/ranges

## Wiring notes
- Strategy plugin registration:
  - `src/strategies/ndx_momentum_rotation/__init__.py`
  - `src/strategies/registry.py` (`_AUTO_IMPORTS`)
- SSOT manager registration:
  - `src/strategies/config/managers/ndx_momentum_rotation_manager.py`
  - `src/strategies/config/managers/__init__.py`
- SSOT YAML source:
  - `src/strategies/ndx_momentum_rotation/ndx_momentum_rotation.yaml`
