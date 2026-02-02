# UI Trace Plan — max_position_loss_pct_equity

## Logs expected
- `actions: ui_loaded_default` (section=core/tunable, val=%r, type=%s, strategy_id, version)
- `actions: ui_param_orig` (from `_compute_overrides`) — original value + type
- `actions: ui_param_raw` (from `_compute_overrides`) — raw UI value + type
- `actions: ui_trigger` (Dash callback_context.triggered)

## Hypotheses under test
1. **Defaults type drift**: Loader returns `int(0)` (instead of float) → overrides not recorded.
2. **UI input returns None/""**: UI never passes a numeric value → value becomes 0.0 or skipped.
3. **Comma parsing issue**: UI provides `"0,03"` as string → conversion fails → fallback/skip.

## Evidence required
- Log lines showing `ui_loaded_default` with section + type
- Log lines showing `ui_param_raw` and `ui_param_orig` for the same save attempt
- Log lines showing `ui_trigger` and which input fired

