# UI Backtest Call-Flow + Strategy Responsibilities (Human Report)

Scope: Dash UI backtest execution path (UI → service → adapter → pipeline → strategy → artifacts) and strategy signal responsibilities with code/line evidence.

## 1) End-to-End Call Flow (UI → Pipeline → Artifacts)

1) **UI Callback Entry**
   - **File:** `trading_dashboard/callbacks/run_backtest_callback.py`  
   - **Func:** `run_backtest(...)`  
   - **Lines:** L41–L209  
   - **Responsibility:** Validate UI inputs, build config snapshot, build run_name, start job.  
   - **Inputs:** `strategy`, `symbols_str`, `timeframe`, `date_mode`, `bt_config_snapshot`  
   - **Outputs:** `job_id`, `run_name`, UI “active_run” store (`run_dir`).

2) **Background Job Start**
   - **File:** `trading_dashboard/services/backtest_service.py`  
   - **Func:** `start_backtest(...)`  
   - **Lines:** L40–L80  
   - **Responsibility:** Create `job_id`, spawn background thread.  
   - **Inputs:** `run_name`, `strategy`, `symbols`, `timeframe`, `start_date`, `end_date`, `config_params`  
   - **Outputs:** `job_id`.

3) **Background Pipeline Execution**
   - **File:** `trading_dashboard/services/backtest_service.py`  
   - **Func:** `_run_pipeline(...)`  
   - **Lines:** L82–L174  
   - **Responsibility:** Call adapter and handle result status.  
   - **Inputs:** `job_id`, `run_name`, `strategy`, `symbols`, `timeframe`, `dates`, `config_params`  
   - **Outputs:** `status`, `run_name`.

4) **Adapter (UI → Pipeline)**
   - **File:** `trading_dashboard/services/new_pipeline_adapter.py`  
   - **Func:** `execute_backtest(...)`  
   - **Lines:** L50–L179  
   - **Responsibility:** Normalize params, compute lookback, build `strategy_meta`, call pipeline.  
   - **Inputs:** `run_name`, `strategy`, `symbols`, `timeframe`, `start_date`, `end_date`, `config_params`  
   - **Outputs:** `status`, `run_dir`.

5) **Pipeline Orchestrator (SSOT)**
   - **File:** `src/axiom_bt/pipeline/runner.py`  
   - **Func:** `run_pipeline(...)`  
   - **Lines:** L27–L220  
   - **Responsibility:** Data fetch → signals → intents → fills → execution → metrics → artifacts.  
   - **Inputs:** `run_id`, `out_dir`, `bars_path`, `strategy_id`, `strategy_version`, `strategy_params`, `strategy_meta`, `compound_*`  
   - **Outputs:** artifacts in `artifacts/backtests/<run_id>/`.

6) **SignalFrame Factory**
   - **File:** `src/axiom_bt/pipeline/signal_frame_factory.py`  
   - **Func:** `build_signal_frame(...)`  
   - **Lines:** L13–L68  
   - **Responsibility:** Strategy dispatch + schema validation.  
   - **Inputs:** `bars`, `strategy_id`, `strategy_version`, `strategy_params`  
   - **Outputs:** `signals_frame`, `schema`.

7) **Strategy Registry / Plugin**
   - **File:** `src/strategies/registry.py`  
   - **Func:** `get_strategy(...)`  
   - **Lines:** L348–L356  
   - **Responsibility:** Load plugin for `insidebar_intraday`.  
   - **Outputs:** `InsideBarPlugin`.

8) **InsideBar Adapter (SignalFrame builder)**
   - **File:** `src/strategies/inside_bar/__init__.py`  
   - **Func:** `extend_insidebar_signal_frame_from_core(...)`  
   - **Lines:** L54–L167  
   - **Responsibility:** Call core, map RawSignal → SignalFrame (signal_side, entry_price, stop_price, take_profit_price).  
   - **Inputs:** `bars`, `params`  
   - **Outputs:** enriched SignalFrame.

9) **InsideBar Core (Pattern + Signals)**
   - **File:** `src/strategies/inside_bar/core.py`  
   - **Func:** `process_data(...)`  
   - **Lines:** L694–L812  
   - **Responsibility:** ATR → inside bar detection → breakout signals → session filter.  
   - **Inputs:** `df`, `symbol`, `config`  
   - **Outputs:** list of `RawSignal`.

10) **Intent Generation**
    - **File:** `src/axiom_bt/pipeline/signals.py`  
    - **Func:** `generate_intent(...)`  
    - **Lines:** L63–L187  
    - **Responsibility:** Map SignalFrame → `events_intent.csv` with valid_from/to and dbg fields.  
    - **Inputs:** `signals_frame`, `strategy_id`, `strategy_version`, `params`  
    - **Outputs:** `events_intent`.

11) **Fill Model**
    - **File:** `src/axiom_bt/pipeline/fill_model.py`  
    - **Func:** `generate_fills(...)`  
    - **Lines:** L35–L164  
    - **Responsibility:** Simulate entry + exit fills from intents/bars.  
    - **Inputs:** `events_intent`, `bars`, `order_validity_policy`, `session_*`  
    - **Outputs:** `fills.csv`.

12) **Execution / Trades**
    - **File:** `src/axiom_bt/pipeline/execution.py`  
    - **Func:** `execute(...)` + `_build_trades(...)`  
    - **Lines:** L212–L265, L41–L199  
    - **Responsibility:** Size fills → build trades → equity/ledger.  
    - **Outputs:** `trades.csv`, `equity_curve.csv`, `portfolio_ledger.csv`.

13) **Metrics + Artifacts**
    - **File:** `src/axiom_bt/pipeline/metrics.py`  
    - **Func:** `compute_and_write_metrics(...)`  
    - **Lines:** L17–L23  
    - **File:** `src/axiom_bt/pipeline/artifacts.py`  
    - **Func:** `write_artifacts(...)`  
    - **Lines:** L24–L57  
    - **Outputs:** `metrics.json`, `run_meta.json`, `run_manifest.json`, `run_result.json`.

## 2) Wo entsteht das Signal?

**Pattern detection + signal generation** happen in:
- `src/strategies/inside_bar/core.py`
  - InsideBar detection: `detect_inside_bars(...)` L183–L248
  - Breakout trigger + signal creation: `generate_signals(...)` L250–L692
  - Pipeline entry: `process_data(...)` L694–L812

**Where signal fields are set:**
- `entry_price`, `stop_loss`, `take_profit`: `generate_signals(...)`  
  - **BUY SL/TP**: L528–L551  
  - **SELL SL/TP**: L620–L643  
  - RawSignal metadata (mother_high/low, atr) L558–L569, L651–L662
- **SignalFrame mapping** happens in `extend_insidebar_signal_frame_from_core(...)`  
  - `signal_side`, `entry_price`, `stop_price`, `take_profit_price`: L123–L127

## 3) Wo greifen Session/Validity/Netting Regeln?

**Session windowing / timezone handling**
- Session gate in core: `generate_signals(...)`  
  - Session filter + tz: L279–L392  
  - Trigger must be in session: L510–L527, L604–L619
  - Final filter: `process_data(...)` L738–L810

**valid_from_policy / valid_to / order_validity_policy**
- Intent validity computed in `generate_intent(...)`  
  - `order_validity_policy=session_end`: L118–L130  
  - `valid_from_policy` + `timeframe_minutes`: L131–L143  
  - `dbg_effective_valid_from_policy`: L112–L117

**Netting / max trades per session**
- In core `generate_signals(...)`:  
  - `max_trades_per_session`: L306–L489  
  - Netting: L310–L508, L576–L591, L669–L680

**SL/TP Calculation**
- In core `generate_signals(...)`  
  - BUY: L528–L551  
  - SELL: L620–L643

## 4) Runtime Evidence (trace)

Trace log: `docs/audits/ui_backtest_trace.log`  
Excerpt: `docs/audits/ui_backtest_trace_excerpt.jsonl`  
Observed sequence matches the static call flow (see `ui_backtest_callflow.md`).
