# UI Backtest Call Flow (Dash → Pipeline)

**Scope:** Dash UI backtest button → background service → pipeline runner → strategy dispatch → intents/fills/trades → artifacts.  
**Sources:** Code inspection (static trace map). Runtime trace log is written to `docs/audits/ui_backtest_trace.log` when `AXIOM_TRACE_UI=1`.

## 1) Static Trace Map (from code)

1. **Dash Callback Entry**
   - **File:** `trading_dashboard/callbacks/run_backtest_callback.py`
   - **Func:** `run_backtest(...)`
   - **Why:** User clicks “Run Backtest”
   - **Key args:** `strategy`, `symbols`, `timeframe`, `date_mode`, `start/end`, `bt_config_snapshot`

2. **Background Job Start**
   - **File:** `trading_dashboard/services/backtest_service.py`
   - **Func:** `BacktestService.start_backtest(...)`
   - **Why:** Run in background thread (non-blocking UI)
   - **Key args:** `run_name`, `strategy`, `symbols`, `timeframe`, `start_date`, `end_date`, `config_params`

3. **Background Pipeline Orchestration**
   - **File:** `trading_dashboard/services/backtest_service.py`
   - **Func:** `BacktestService._run_pipeline(...)`
   - **Why:** Actual execution for job_id
   - **Key args:** same as above + `job_id`

4. **Adapter (UI → Pipeline)**
   - **File:** `trading_dashboard/services/new_pipeline_adapter.py`
   - **Func:** `NewPipelineAdapter.execute_backtest(...)`
   - **Why:** SSOT modular pipeline entry
   - **Key args:** `run_name`, `strategy`, `symbols`, `timeframe`, `start_date`, `end_date`, `config_params`

5. **Pipeline Runner (SSOT)**
   - **File:** `src/axiom_bt/pipeline/runner.py`
   - **Func:** `run_pipeline(...)`
   - **Why:** Orchestrates end-to-end pipeline
   - **Key args:** `run_id`, `out_dir`, `bars_path`, `strategy_id`, `strategy_version`, `strategy_params`, `strategy_meta`, `compound_*`

6. **SignalFrame Factory**
   - **File:** `src/axiom_bt/pipeline/signal_frame_factory.py`
   - **Func:** `build_signal_frame(...)`
   - **Why:** Strategy dispatch + schema validation
   - **Key args:** `bars`, `strategy_id`, `strategy_version`, `strategy_params`

7. **Strategy Dispatch**
   - **File:** `src/strategies/registry.py`
   - **Func:** `get_strategy(strategy_id)`
   - **Why:** Load plugin for `insidebar_intraday`
   - **Key args:** `strategy_id`

8. **InsideBar Strategy Plugin**
   - **File:** `src/strategies/inside_bar/__init__.py`
   - **Func:** `InsideBarPlugin.extend_signal_frame(...)`
   - **Why:** Build signal frame from bars via core
   - **Key args:** `bars`, `params`

9. **Intent Generation**
   - **File:** `src/axiom_bt/pipeline/signals.py`
   - **Func:** `generate_intent(...)`
   - **Why:** Convert signal frame into `events_intent.csv`
   - **Key args:** `signals_frame`, `strategy_id`, `strategy_version`, `strategy_params`

10. **Fill Model**
    - **File:** `src/axiom_bt/pipeline/fill_model.py`
    - **Func:** `generate_fills(...)`
    - **Why:** Create fills from intents + bars
    - **Key args:** `events_intent`, `bars`, `order_validity_policy`, `session_timezone`, `session_filter`

11. **Execution / Trades**
    - **File:** `src/axiom_bt/pipeline/execution.py`
    - **Func:** `execute(...)`
    - **Why:** Apply sizing, derive trades, equity, ledger
    - **Key args:** `fills`, `events_intent`, `bars`, `initial_cash`, `compound_enabled`, `session_*`

12. **Metrics + Artifacts**
    - **Files:** `src/axiom_bt/pipeline/metrics.py`, `src/axiom_bt/pipeline/artifacts.py`
    - **Funcs:** `compute_and_write_metrics(...)`, `write_artifacts(...)`
    - **Why:** Persist metrics + CSVs + run_meta/run_manifest/run_result

---

## 2) Runtime Trace (when AXIOM_TRACE_UI=1)

**Log file:** `docs/audits/ui_backtest_trace.log`  
Each line is JSON with keys: `ts`, `step`, `run_id`, `strategy_id`, `strategy_version`, `file`, `func`, `extra`.

### Observed runtime sequence (run_id=260131_003429_HOOD_IB_trace3_300d)
1. `ui_callback_entry`
2. `ui_start_backtest`
3. `service_start_backtest`
4. `service_run_pipeline_start`
5. `adapter_execute_backtest_start`
6. `adapter_call_run_pipeline`
7. `pipeline_run_start`
8. `signal_frame_factory_start`
9. `strategy_loaded`
10. `pipeline_signal_frame_built`
11. `pipeline_intent_generated`
12. `pipeline_fills_generated`
13. `pipeline_execution_done`
14. `pipeline_write_artifacts`
15. `adapter_run_pipeline_done`
16. `service_run_pipeline_done`

**Trace excerpt (first 20 lines for run_id=260131_003429_HOOD_IB_trace3_300d):**
```
{"ts": "2026-01-30T23:34:29Z", "step": "ui_callback_entry", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": null, "file": "/home/mirko/data/workspace/droid/traderunner/trading_dashboard/callbacks/run_backtest_callback.py", "func": "run_backtest", "extra": {}}
{"ts": "2026-01-30T23:34:29Z", "step": "service_start_backtest", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": null, "file": "/home/mirko/data/workspace/droid/traderunner/trading_dashboard/services/backtest_service.py", "func": "start_backtest", "extra": {"job_id": "260131_003429_HOOD_IB_trace3_300d_20260131_003429"}}
{"ts": "2026-01-30T23:34:29Z", "step": "ui_start_backtest", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/trading_dashboard/callbacks/run_backtest_callback.py", "func": "run_backtest", "extra": {"job_id": "260131_003429_HOOD_IB_trace3_300d_20260131_003429"}}
{"ts": "2026-01-30T23:34:29Z", "step": "service_run_pipeline_start", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": null, "file": "/home/mirko/data/workspace/droid/traderunner/trading_dashboard/services/backtest_service.py", "func": "_run_pipeline", "extra": {"job_id": "260131_003429_HOOD_IB_trace3_300d_20260131_003429"}}
{"ts": "2026-01-30T23:34:29Z", "step": "adapter_execute_backtest_start", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/trading_dashboard/services/new_pipeline_adapter.py", "func": "execute_backtest", "extra": {}}
{"ts": "2026-01-30T23:34:29Z", "step": "adapter_call_run_pipeline", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/trading_dashboard/services/new_pipeline_adapter.py", "func": "execute_backtest", "extra": {}}
{"ts": "2026-01-30T23:34:29Z", "step": "pipeline_run_start", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/src/axiom_bt/pipeline/runner.py", "func": "run_pipeline", "extra": {}}
{"ts": "2026-01-30T23:34:29Z", "step": "signal_frame_factory_start", "run_id": null, "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/src/axiom_bt/pipeline/signal_frame_factory.py", "func": "build_signal_frame", "extra": {}}
{"ts": "2026-01-30T23:34:29Z", "step": "strategy_loaded", "run_id": null, "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/src/axiom_bt/pipeline/signal_frame_factory.py", "func": "build_signal_frame", "extra": {}}
{"ts": "2026-01-30T23:34:31Z", "step": "pipeline_signal_frame_built", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/src/axiom_bt/pipeline/runner.py", "func": "run_pipeline", "extra": {"rows": 15990}}
{"ts": "2026-01-30T23:34:31Z", "step": "pipeline_intent_generated", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/src/axiom_bt/pipeline/runner.py", "func": "run_pipeline", "extra": {"rows": 308}}
{"ts": "2026-01-30T23:34:31Z", "step": "pipeline_fills_generated", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/src/axiom_bt/pipeline/runner.py", "func": "run_pipeline", "extra": {"rows": 616}}
{"ts": "2026-01-30T23:34:31Z", "step": "pipeline_execution_done", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/src/axiom_bt/pipeline/runner.py", "func": "run_pipeline", "extra": {"trades": 308}}
{"ts": "2026-01-30T23:34:31Z", "step": "pipeline_write_artifacts", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/src/axiom_bt/pipeline/runner.py", "func": "run_pipeline", "extra": {}}
{"ts": "2026-01-30T23:34:31Z", "step": "adapter_run_pipeline_done", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": "1.0.1", "file": "/home/mirko/data/workspace/droid/traderunner/trading_dashboard/services/new_pipeline_adapter.py", "func": "execute_backtest", "extra": {}}
{"ts": "2026-01-30T23:34:31Z", "step": "service_run_pipeline_done", "run_id": "260131_003429_HOOD_IB_trace3_300d", "strategy_id": "insidebar_intraday", "strategy_version": null, "file": "/home/mirko/data/workspace/droid/traderunner/trading_dashboard/services/backtest_service.py", "func": "_run_pipeline", "extra": {"job_id": "260131_003429_HOOD_IB_trace3_300d_20260131_003429", "status": "success"}}
```

### Steps observed (expected order)
1. `ui_callback_entry`
2. `ui_start_backtest`
3. `service_start_backtest`
4. `service_run_pipeline_start`
5. `adapter_execute_backtest_start`
6. `adapter_call_run_pipeline`
7. `pipeline_run_start`
8. `signal_frame_factory_start`
9. `strategy_loaded`
10. `pipeline_signal_frame_built`
11. `pipeline_intent_generated`
12. `pipeline_fills_generated`
13. `pipeline_execution_done`
14. `pipeline_write_artifacts`
15. `adapter_run_pipeline_done`
16. `service_run_pipeline_done`

---

## 3) How to Generate Trace Log

1. Start Dash with tracing enabled:
   ```bash
   AXIOM_TRACE_UI=1 PYTHONPATH=src:. python -m trading_dashboard.app
   ```
2. Trigger a backtest from UI (any small run).
3. Check log:
   ```
   docs/audits/ui_backtest_trace.log
   ```
