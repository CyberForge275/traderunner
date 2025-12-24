# Trade Inspector

Provides audit-grade visualization for backtest runs.

## Artifacts
- `bars/bars_exec_<TF>_rth.parquet`: RTH-only exec timeframe bars (tz-aware)
- `bars/bars_signal_<TF>_rth.parquet`: Optional signal timeframe bars
- `bars/bars_slice_meta.json`: meta (tz, timeframe, warmup)
- `trade_evidence.csv`: per-trade evidence codes (proof_status, entry/exit proven)

## Running locally
```
PYTHONPATH=".:src" .venv/bin/python trading_dashboard/app.py
```
Open `http://localhost:9001` → tab “Trade Inspector”.

## Evidence codes
- `proof_status`: PROVEN | PARTIAL | NO_PROOF
- `entry_exec_proven` / `exit_exec_proven`: YES | NO | UNKNOWN
- `rth_compliant`: YES | NO | UNKNOWN
- `data_slice_integrity`: OK | MISSING_BARS

## Tests
```
PYTHONPATH=src:. pytest -q tests/dashboard/test_trade_repository.py \
    tests/dashboard/test_trade_evidence_engine.py \
    tests/dashboard/test_trade_detail_service.py
```
