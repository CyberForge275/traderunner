# API Specification (Frozen Public Interfaces)

Contract scope: two public interfaces are documented and frozen:
1) Uvicorn HTTP API (`marketdata-monorepo`)
2) Batch/CLI pipeline API (`traderunner`)

This document captures the current runtime behavior without changing semantics.

## A) Overview

- Contract version: `2026-02-26`
- Repos:
  - `~/data/workspace/droid/marketdata-monorepo`
  - `~/data/workspace/droid/traderunner`
- Strategy lifecycle and immutability: see `docs/FACTORY_LABS_AND_STRATEGY_LIFECYCLE.md`.
- Market timezone semantics:
  - Strategy/runtime timezone is provided by config (`session_timezone`)
  - Session window for `rth` is resolved by marketdata service config (`session_windows.yaml`)

## B) Uvicorn HTTP API Spec (marketdata-monorepo)

### B.1 Runtime entrypoint

- App object: `~/data/workspace/droid/marketdata-monorepo/src/app.py:18`
- Uvicorn target: `app:app` (from `src/` working directory)

Example:

```bash
cd ~/data/workspace/droid/marketdata-monorepo/src
uvicorn app:app --host 0.0.0.0 --port 8010
```

### B.2 Endpoint index

| Method | Path | Purpose | Request model | Response model | Auth |
|---|---|---|---|---|---|
| POST | `/ensure_bars` | Ensure HTTP M1 base coverage; backfill if needed | `EnsureBarsRequest` | `EnsureBarsResponse` | none |
| POST | `/ensure_timeframe_bars` | Ensure+build derived timeframe parquet (M1/M5/M15/H1) | `EnsureTimeframeBarsRequest` | `EnsureTimeframeBarsResponse` | none |

Source: `~/data/workspace/droid/marketdata-monorepo/src/app.py:70,140`

### B.3 Request/response models

#### POST `/ensure_bars`

Request (`EnsureBarsRequest`, all required):
- `symbol: str` (`min_length=1`)
- `start_date: str` (ISO date string, `YYYY-MM-DD` accepted)
- `end_date: str`
- `timeframe_minutes: int` (`1..240`)
- `session_timezone: str`
- `session_mode: str`

Source: `~/data/workspace/droid/marketdata-monorepo/src/app.py:34-41`

Response (`EnsureBarsResponse`):
- `status: str` (`ok` | `backfilled` | `error`)
- `gaps_before: list[dict]`
- `gaps_after: list[dict]`
- `details: dict`

Source: `~/data/workspace/droid/marketdata-monorepo/src/app.py:43-48`

Behavior notes:
- Coverage check before/after via `check_http_m1_coverage`
- Backfill path uses EODHD token from environment
- On missing token returns JSON payload with `status="error"` (HTTP 200)

Source: `~/data/workspace/droid/marketdata-monorepo/src/app.py:77-137`

Example:

```bash
curl -X POST http://localhost:8010/ensure_bars \
  -H 'content-type: application/json' \
  -d '{
    "symbol":"HOOD",
    "start_date":"2025-12-01",
    "end_date":"2025-12-31",
    "timeframe_minutes":1,
    "session_timezone":"America/New_York",
    "session_mode":"rth"
  }'
```

#### POST `/ensure_timeframe_bars`

Request (`EnsureTimeframeBarsRequest`, all required):
- `symbol: str` (`min_length=1`)
- `start_date: str`
- `end_date: str`
- `timeframe_minutes: int` (`1..240`)
- `session_timezone: str`
- `session_mode: str`

Source: `~/data/workspace/droid/marketdata-monorepo/src/app.py:50-57`

Response (`EnsureTimeframeBarsResponse`):
- `status: str` (`ok` | `backfilled` | `error`)
- `gaps_before: list[dict]`
- `gaps_after: list[dict]`
- `details: dict` containing at least:
  - `data_root`, `derived_path`, `session_mode`, `session_timezone`
  - `effective_session_window` (`null` for raw; `{tz,start,end}` for rth)
  - `rows`, `ts_min`, `ts_max`, `effective_start`, `effective_end`, `coverage_ok`

Source: `~/data/workspace/droid/marketdata-monorepo/src/app.py:171-188`

Behavior notes:
- Delegates to `ensure_and_build_bars(...)`
- Exceptions are converted into `status="error"` response payloads

Source: `~/data/workspace/droid/marketdata-monorepo/src/app.py:147-169`

Example:

```bash
curl -X POST http://localhost:8010/ensure_timeframe_bars \
  -H 'content-type: application/json' \
  -d '{
    "symbol":"HOOD",
    "start_date":"2025-12-01",
    "end_date":"2025-12-31",
    "timeframe_minutes":15,
    "session_timezone":"America/New_York",
    "session_mode":"rth"
  }'
```

### B.4 Effective session window contract

- SSOT file: `~/data/workspace/droid/marketdata-monorepo/src/marketdata_service/config/session_windows.yaml`
- Resolver: `~/data/workspace/droid/marketdata-monorepo/src/marketdata_service/session_windows.py:22-40`
- Semantics:
  - `session_mode=raw` => no filter (`effective_session_window = null`)
  - `session_mode=rth` => lookup by `session_timezone`; unknown timezone fails fast

### B.5 OpenAPI

- Standard FastAPI docs endpoints are available by default:
  - `/openapi.json`
  - `/docs`
- No static OpenAPI snapshot is currently committed.

## C) Pipeline API Spec (traderunner)

### C.1 Public entrypoints

1) Headless CLI:
- File: `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/cli.py`
- Command:

```bash
cd ~/data/workspace/droid/traderunner
PYTHONPATH=src:. python -m axiom_bt.pipeline.cli \
  --run-id RUN_001 \
  --out-dir artifacts/backtests/RUN_001 \
  --bars-path artifacts/backtests/RUN_001/bars_snapshot.parquet \
  --strategy-id insidebar_intraday \
  --strategy-version 1.0.1 \
  --symbol HOOD \
  --timeframe M5 \
  --requested-end 2026-02-20 \
  --lookback-days 40
```

2) Dashboard adapter (UI -> same pipeline):
- Adapter: `~/data/workspace/droid/traderunner/trading_dashboard/services/new_pipeline_adapter.py:75`
- Calls `run_pipeline(...)`: `.../new_pipeline_adapter.py:307`

3) Core orchestrator API:
- Function: `run_pipeline(...)`
- File: `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/runner.py:141`

### C.2 CLI contract

Required CLI args:
- `--run-id`
- `--out-dir`
- `--bars-path`
- `--strategy-id`
- `--strategy-version`
- `--symbol`
- `--timeframe`
- `--requested-end` (or `--valid-to` alias)
- `--lookback-days` (or derive from `--valid-from`)

Source: `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/cli.py:26-44,60-80`

Optional CLI args:
- `--base-config`
- `--valid-from-policy`
- `--order-validity-policy`
- `--compound-enabled`
- `--compound-equity-basis`
- `--initial-cash`
- `--fees-bps`
- `--slippage-bps`

Source: `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/cli.py:29-52`

### C.3 Inputs (pipeline)

Primary logical inputs:
- bars snapshot path (or auto-ensure path if missing)
- strategy identity + version + resolved params
- timeframe and time range (`requested_end`, `lookback_days`)
- session semantics (`session_mode`, `session_timezone` from strategy core)
- base config (`backtest_pipeline_defaults.yaml`) + override stacks

### C.4 Outputs/artifacts

Writer implementation:
- `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/artifacts.py:28-63`

Always written by `write_artifacts(...)`:
- `signals_frame.csv`
- `events_intent.csv`
- `fills.csv`
- `trades.csv`
- `equity_curve.csv`
- `portfolio_ledger.csv`
- `metrics.json`
- `run_manifest.json`
- `run_result.json`
- `run_meta.json`

Manifest index baseline in runner:
- `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/runner.py:460-469`

### C.5 Error/exit behavior

CLI:
- `main()` returns `0` on success
- Input validation failures use `SystemExit(...)`
- uncaught pipeline failures bubble as process failure (non-zero exit)

Source: `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/cli.py:55-124`

UI adapter statuses (`new_pipeline_adapter.execute_backtest`):
- `success`
- `failed_precondition`
- `error`
- `failed`

Source: `~/data/workspace/droid/traderunner/trading_dashboard/services/new_pipeline_adapter.py:99-104,173-231`

## D) Defaults Table (current behavior + source)

| Parameter | Default | Source |
|---|---|---|
| `cli.base_config` | `configs/runs/backtest_pipeline_defaults.yaml` if file exists | `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/cli.py:13-16,33` |
| `cli.compound_equity_basis` | `cash_only` | `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/cli.py:47` |
| `cli.initial_cash` | `10000.0` | `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/cli.py:48` |
| `cli.fees_bps` | `None` (then pipeline call currently maps to `0.0`) | `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/cli.py:50,112` |
| `cli.slippage_bps` | `None` (then pipeline call currently maps to `0.0`) | `~/data/workspace/droid/traderunner/src/axiom_bt/pipeline/cli.py:51,113` |
| `backtest.initial_cash` | `10000` | `~/data/workspace/droid/traderunner/configs/runs/backtest_pipeline_defaults.yaml:2` |
| `backtest.fixed_qty` | `0` | `~/data/workspace/droid/traderunner/configs/runs/backtest_pipeline_defaults.yaml:3` |
| `costs.commission_bps` | `2.0` | `~/data/workspace/droid/traderunner/configs/runs/backtest_pipeline_defaults.yaml:6` |
| `costs.slippage_bps` | `1.0` | `~/data/workspace/droid/traderunner/configs/runs/backtest_pipeline_defaults.yaml:7` |
| `execution.allow_same_bar_exit` | `true` | `~/data/workspace/droid/traderunner/configs/runs/backtest_pipeline_defaults.yaml:12` |
| `execution.same_bar_resolution_mode` | `m1_probe_then_no_fill` | `~/data/workspace/droid/traderunner/configs/runs/backtest_pipeline_defaults.yaml:13` |
| `execution.intrabar_probe_timeframe` | `M1` | `~/data/workspace/droid/traderunner/configs/runs/backtest_pipeline_defaults.yaml:14` |
| `marketdata.exchange` | `US` if env missing | `~/data/workspace/droid/marketdata-monorepo/src/marketdata_service/http_bars_builder.py:129` |
| `rth session window` | `09:30-16:00` for `America/New_York` | `~/data/workspace/droid/marketdata-monorepo/src/marketdata_service/config/session_windows.yaml:2-4` |

## E) Compatibility rules (technical)

- Existing fields/endpoints are frozen; changes must be additive.
- Artifact file names are public contract surfaces and must not be renamed without versioned migration.
- Strategy behavior changes require strategy version bump (immutable finalized versions).
- New optional fields in JSON/CSV are allowed if old consumers continue parsing existing fields unchanged.
