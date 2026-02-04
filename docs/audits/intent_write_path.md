# Intent write path

## Write location
- `src/axiom_bt/pipeline/artifacts.py:28-45` — `write_artifacts(...)` writes `events_intent.csv` via `write_frame(events_intent, out_dir / "events_intent.csv")`.

## Producer location
- `src/axiom_bt/pipeline/signals.py:63-177` — `generate_intent(...)` builds the `events_intent` DataFrame from `signals_frame` + params.
- `src/axiom_bt/pipeline/runner.py:190-224` — `run_pipeline(...)` calls `generate_intent(...)`, then passes `events_intent` to `fill_model.generate_fills(...)` and `execution.execute(...)`.

## Inputs
- `signals_frame` built by `build_signal_frame(...)` (`src/axiom_bt/pipeline/signal_frame_factory.py:16-90`) using strategy plugin (`src/strategies/inside_bar/__init__.py:88-185`).
- `params` from pipeline runner (`src/axiom_bt/pipeline/runner.py:246-268` manifest fields) include `order_validity_policy`, `session_timezone`, `session_filter`, `valid_from_policy`, `timeframe_minutes`.

## Evidence commands
- `nl -ba src/axiom_bt/pipeline/signals.py | sed -n '63,190p'`
- `nl -ba src/axiom_bt/pipeline/runner.py | sed -n '180,260p'`
- `nl -ba src/axiom_bt/pipeline/artifacts.py | sed -n '28,58p'`
