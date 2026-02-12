# Evidence Pack: UI -> Single Pipeline Data Entrypoint

## Scope
Hard evidence that Backtests UI uses one deterministic path:

`UI -> BacktestService -> NewPipelineAdapter -> run_pipeline -> ensure_and_snapshot_bars`

and that coverage/gap checks happen in one place.

## 1) UI start -> BacktestService
- `trading_dashboard/callbacks/run_backtest_callback.py:249`
```python
job_id = service.start_backtest(
    run_name=run_name,
    strategy=strategy,
    symbols=symbols,
    timeframe=timeframe,
    start_date=start_date_str,
    end_date=end_date_str,
    config_params=config_params if config_params else None,
)
```

## 2) BacktestService -> NewPipelineAdapter
- `trading_dashboard/services/backtest_service.py:126`
```python
from .new_pipeline_adapter import create_new_adapter
```
- `trading_dashboard/services/backtest_service.py:144`
```python
result = adapter.execute_backtest(
    run_name=run_name,
    strategy=strategy,
    symbols=symbols,
    timeframe=timeframe,
    start_date=start_date,
    end_date=end_date,
    config_params=config_params
)
```

## 3) Adapter -> single pipeline entry (`run_pipeline`)
- `trading_dashboard/services/new_pipeline_adapter.py:180`
```python
run_pipeline(
    run_id=run_name,
    out_dir=run_dir,
    bars_path=bars_snapshot_path,
    strategy_id=strategy,
    strategy_version=strategy_version,
    strategy_params=strategy_params_with_meta,
    strategy_meta={...},
    ...
)
```

## 4) Pipeline entry -> single data gate
- `src/axiom_bt/pipeline/runner.py:138`
```python
snap_info = ensure_and_snapshot_bars(
    run_dir=out_dir,
    symbol=strategy_params.get("symbol", "UNKNOWN"),
    timeframe=strategy_params.get("timeframe", "M5"),
    requested_end=requested_end,
    lookback_days=int(lookback_days),
    ...
)
```

This is the only data-ensure call in `run_pipeline` before loading bars snapshot.

## 5) Coverage/gap check location (single gate logic)
- `src/axiom_bt/pipeline/data_fetcher.py:153`
```python
coverage = check_local_m1_coverage(
    symbol=symbol,
    start=effective_start.date().isoformat(),
    end=end_ts.date().isoformat(),
    tz=market_tz,
)
```
- `src/axiom_bt/pipeline/data_fetcher.py:159`
```python
if coverage.get("has_gap") and (
    not auto_fill_gaps or not legacy_http_backfill_allowed
):
```
- `src/axiom_bt/pipeline/data_fetcher.py:172`
```python
raise MissingHistoricalDataError(
    f"{reason} for {symbol} range={requested_range}; "
    f"gaps={coverage.get('gaps', [])}. {hint}"
)
```

Gap reasons are produced in:
- `src/axiom_bt/intraday.py:145` -> `before_existing_data`
- `src/axiom_bt/intraday.py:156` -> `after_existing_data`

## 6) Evidence: legacy fetchers exist but are not used by UI pipeline path

### Legacy/alternate producers (found in repo)
- `src/axiom_bt/data/eodhd_fetch.py` (HTTP fetch implementation; referenced by intraday/cli tools)
- `src/axiom_bt/intraday.py:317` and `src/axiom_bt/intraday.py:366` call `fetch_intraday_1m_to_parquet(...)`
- `trading_dashboard/data_loading/loaders/eodhd_backfill.py` exists but is hard-disabled in constructor:
  - `trading_dashboard/data_loading/loaders/eodhd_backfill.py:26`
```python
raise MissingHistoricalDataError(...)
```

### UI path grep evidence (no direct use in UI execution chain files)
Command:
```bash
rg -n "eodhd_backfill|database_loader|axiom_bt.data.eodhd_fetch|fetch_intraday|IntradayStore|check_local_m1_coverage|axiom_bt.intraday" \
  trading_dashboard/callbacks/run_backtest_callback.py \
  trading_dashboard/services/backtest_service.py \
  trading_dashboard/services/new_pipeline_adapter.py -S
```
Result: no matches.

## 7) Conclusion
- UI backtest path enters data handling exactly via `ensure_and_snapshot_bars(...)` in `run_pipeline`.
- Coverage/gap decision is centralized in `ensure_and_snapshot_bars -> check_local_m1_coverage`.
- Legacy fetch components are present in repo but not directly invoked by the UI execution chain.
