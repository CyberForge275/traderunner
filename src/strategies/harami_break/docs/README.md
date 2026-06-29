# Harami Break Strategy Documentation

Status: Draft / scaffolded strategy package

## SSOT Configuration

Primary YAML:
- `src/strategies/harami_break/harami_break_intraday.yaml`

Current strategy/version:
- `strategy_id: harami_break_intraday`
- `version: 1.0.0`

## Current Core Parameters (v1.0.0)

- `session_timezone` (enum):
  - `America/New_York`
  - `Europe/Berlin`
- `session_windows` (list of `HH:MM-HH:MM` strings)
- `inside_bar_definition_mode` (enum):
  - `mb_body_oc__ib_hl`
  - `mb_body_oc__ib_body`
  - `mb_range_hl__ib_hl`
  - `mb_high__ib_high_and_close_in_mb_range`
- `regime_filter` (mapping):
  - `enabled` (bool)
  - `allow_gg_short` (bool)
  - `allow_mixed_short` (bool)
- `entry_level_mode` (enum):
  - `mother_bar`
  - `inside_bar`
- `max_trades_per_session_window` (int >= 1)
- `order_validity_policy` (enum):
  - `session_end`
  - `fixed_minutes`
  - `fixed_bars`
- `order_validity_minutes` (int, min 1, max 60)
- `order_validity_bars` (int, min 1, max 10)
- `trailing` (mapping):
  - `enabled` (bool)
  - `trigger_tp_pct` (float > 0)
  - `risk_remaining_pct` (float >= 0)
  - `apply_mode` (enum: `next_bar`, `same_bar`)

## Notes on Current Scope

- `required_warmup_bars` is intentionally omitted for this strategy version.
- `inside_bar_mode` is intentionally omitted for this strategy version.
- `tunable` is currently empty in v1.0.0.
- Strategy runtime implementation is still placeholder (`strategy.py` raises `NotImplementedError`).

## Regime Filter Semantics

When `regime_filter.enabled=true`, short intents are gated by candle-color regime:
- `GG` (green mother + green inside): short only if `allow_gg_short=true`
- `mixed` (green/red or red/green): short only if `allow_mixed_short=true`
- other regimes (`RR`, doji/unknown): unchanged

Long intents are not filtered by this gate.

## events_intent Reporting Fields (additive)

Harami now writes full level snapshots per intent row (no execution logic change):
- `sig_LONG_entry_price`, `sig_LONG_stop_price`, `sig_LONG_take_profit_price`
- `sig_SHORT_entry_price`, `sig_SHORT_stop_price`, `sig_SHORT_take_profit_price`

Pattern context for inspector/audit:
- `dbg_mother_ts`, `dbg_inside_ts`
- `dbg_mother_high`, `dbg_mother_low`, `dbg_mother_range`

## Rollback Procedure (explicit)

If performance degrades, rollback is deterministic:
1. Revert configuration toggle only:
   - set `regime_filter.enabled: false` in `harami_break_intraday.yaml`
   - keep code unchanged, rerun regression.
2. If full rollback is required:
   - checkout tag `stable-20260227-1129-pre-regime-filter`
   - rerun the same backtests for parity verification.

## UI Behavior

- Strategy is visible in SSOT Config Viewer via config-manager registry.
- `session_timezone` is rendered as dropdown (enum-backed field spec).
- `trailing` is rendered as a master/slave grouped input and persisted as mapping.

## Relevant Files

- Config spec: `src/strategies/config/specs/harami_break_spec.py`
- Config manager: `src/strategies/config/managers/harami_break_manager.py`
- Pattern rules: `src/strategies/harami_break/rules.py`
- Pattern adapter: `src/strategies/harami_break/pattern_detection.py`

## Validation/Test Pointers

- `src/strategies/harami_break/tests/test_rules.py`
- `tests/test_ui_overrides_trailing_mapping.py`
- `tests/test_strategy_config_field_specs_api.py`
