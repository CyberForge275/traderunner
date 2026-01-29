## SignalFrame Contract V1 (Pipeline)

- SSOT for signal DataFrames used by the pipeline (not YAML). Columns are defined in Python schema hooks.
- Strategies add indicators/flags only; order generation is *not* allowed here.
- Base columns: `timestamp (UTC)`, `open`, `high`, `low`, `close`, `volume`.
- Generic columns: `symbol`, `timeframe`, `strategy_id`, `strategy_version`, `strategy_tag`.
- Strategy columns: hook-specific (e.g., insidebar adds `ib__*`, `sig_*`).
- Invariants: timestamp tz-aware UTC; `sig_long`/`sig_short` not both true; `sig_side` consistent; non-null where required.

### Adding a new strategy hook
1) Implement `StrategySignalHook` subclass under `axiom_bt/strategy_hooks/`.
2) Define `get_signal_frame_schema(version)` returning `SignalFrameSchemaV1` with ColumnSpecs.
3) Implement `extend_signal_frame(bars, params)` producing deterministic columns from bars+params.
4) Register the hook in `strategy_hooks/registry.py`.
5) Add tests: contract validation, factory build, registry resolution.

### Pipeline usage
- `build_signal_frame(...)` resolves hook, calls `extend_signal_frame`, validates with Contract V1, and logs `actions: signal_frame_built`.
- YAML remains parameters-only; column schema lives in hook code.
