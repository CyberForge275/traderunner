# BACKTESTING INTERFACE CONTRACT (axiom_bt)

**Status:** Normative Contract
**Audience:** Strategy authors, engine implementers, audit/verification tooling, dashboard consumers
**Primary Goal:** Make backtests bullet-proof, deterministic, auditable, and timezone/session consistent.

---

## 0. Scope

This contract defines the required interfaces, invariants, artifacts, and timestamp semantics for three backtest modes:

1. **Intraday Backtesting (INTRADAY):** signals and execution are intraday timeframes (e.g., signal=M5/M15, execution=M1).

2. **Daytrading Backtesting (DAYTRADING):** same as intraday but no overnight risk — open positions must be closed by EOD (RTH end) unless explicitly configured otherwise.

3. **Hybrid Daily→Intraday (HYBRID):** signal is computed on daily close (D1); entry/SL/TP execution uses intraday (M1 preferred, M5 allowed) on the next trading day.

This contract is **strategy-agnostic**. Strategy-specific logic (Inside Bar, etc.) plugs into these interfaces and must obey these invariants.

---

## 1. Definitions

### 1.1 Timezones

- **market_tz:** The exchange timezone for simulation (default: `America/New_York` for US equities).
- **storage_tz:** The canonical artifact timestamp timezone (recommended: UTC), but must be consistent across all artifacts.
- **display_tz:** UI-only timezone conversion (must not affect simulation).

> **Invariant TZ-1:** Simulation logic must be executed on a single, explicit time axis. No mixed tz in a single DataFrame.

### 1.2 Sessions / RTH

- **RTH (Regular Trading Hours):** 09:30–16:00 `market_tz` (unless instrument registry says otherwise).
- **Pre/Aftermarket:** must be excluded from candle generation and backtest history by default.

> **Invariant RTH-1:** Candle generation and backtesting must use RTH-only bars (no pre/post).
> **Invariant RTH-2:** Any run that uses non-RTH data must explicitly declare it (`allow_extended_hours=true`) and must mark evidence as degraded.

### 1.3 Bar timestamp semantics

For a bar series with timeframe TF:

- `ts` represents the bar start (left-labeled) in `market_tz` (or `storage_tz` but convertible).
- The bar covers `[ts, ts+TF)`.

> **Invariant BAR-1:** All bar series must explicitly declare `label` and `closed` behavior in run metadata (recommended: `label=left`, `closed=left` or `closed=right`, but must be consistent and documented).
> **Invariant BAR-2:** Signal timestamps must align to the signal grid implied by the resampling.

### 1.4 Order execution semantics (touch rules)

Unless explicitly overridden by a strategy:

- **Long TP** is hit if `bar_high >= tp_level`
- **Long SL** is hit if `bar_low <= sl_level`
- **Short TP** is hit if `bar_low <= tp_level`
- **Short SL** is hit if `bar_high >= sl_level`

> **Invariant EXEC-1 (Earliest-touch):** Entries and exits are executed on the **earliest bar** that satisfies the touch condition on the execution timeframe.
> **Invariant EXEC-2:** Fills must be price-plausible: the fill price must be within the bar's `[low, high]` (after applying slippage model rules if the model can push beyond). Any exception must be documented and flagged in evidence.

---

## 2. Backtest Modes

### 2.1 INTRADAY Mode

**Inputs:**
- `symbol`
- `signal_tf` (e.g., M5, M15)
- `exec_tf` (e.g., M1 or M5)
- `start_ts`, `end_ts` (tz-aware)
- strategy parameters

**Behavior:**
1. Load intraday OHLCV at `exec_tf` (or M1 base then resample).
2. Create signal bars at `signal_tf`.
3. Generate signals on `signal_tf`.
4. Convert signals to orders with explicit validity windows.
5. Execute on `exec_tf` using earliest-touch.
6. Persist all artifacts (orders, fills, trades, bars, steps, meta).

> **Invariant INTRA-1:** If `exec_tf` is M1, fill timestamps may occur at any minute during RTH.
> **Invariant INTRA-2:** Signal timestamps must align to `signal_tf` grid.

### 2.2 DAYTRADING Mode

Same as INTRADAY, plus:

> **Invariant DAY-1:** No positions may remain open beyond the trading day (RTH end) unless explicitly configured.
> **Invariant DAY-2:** If neither TP nor SL is hit intraday, exit must occur via EOD policy (e.g., close at last exec bar or defined EOD time).

### 2.3 HYBRID Daily→Intraday Mode (Final Decision)

#### Daily Signal

On day D at daily close, compute:
- `signal_side` ∈ {LONG, SHORT, NONE}
- `entry_level` (only for the chosen direction)
- optionally `sl_level`, `tp_level` (fixed or derived)

**Single-direction invariant:**

> **Invariant HYB-1:** A daily signal must never be both LONG and SHORT. Exactly one of:
> - LONG + long entry level
> - SHORT + short entry level
> - NONE

#### Next-day Execution

On day D+1 during RTH only:
- If LONG: enter at earliest `exec_tf` bar where `bar_high >= entry_level`
- If SHORT: enter at earliest bar where `bar_low <= entry_level`
- SL/TP monitored on `exec_tf` using earliest-touch semantics.
- **Expiry:** if entry not triggered by end of day (default), mark as expired.

> **Invariant HYB-2:** Hybrid entry can only occur on the **next trading day** after signal generation (no same-day intraday entry).
> **Invariant HYB-3:** Hybrid execution timeframe is M1 preferred; M5 allowed when configured, but must be declared in metadata.

---

## 3. Data Requirements and Normalization

### 3.1 OHLCV column standard

All OHLCV columns must be lowercase:
```
open, high, low, close, volume
```
Index/time column: `ts` (tz-aware).

> **Invariant DATA-1:** Lowercase OHLCV is the SSOT format across all modules.

### 3.2 Missing data / gaps

- Backtests must validate data continuity on the `market_tz` RTH axis.
- Gap detection must not compare a UTC window against a `market_tz` window incorrectly.

> **Invariant DATA-2:** Gap checks must be performed after converting timestamps into `market_tz` and applying RTH filter.

---

## 4. Artifacts: Required Outputs and Schemas

All runs persist artifacts under:
```
artifacts/backtests/<run_id>/
```

### 4.1 run_meta.json (required)

Must include:
- `run_id`, `symbol`, `mode` (INTRADAY|DAYTRADING|HYBRID)
- `market_tz`, `storage_tz`, `rth_start`, `rth_end`, `rth_enforced`
- `signal_tf`, `exec_tf`, `daily_tf` (if hybrid)
- `bar_label`, `bar_closed`, resampling parameters
- `git_sha`, `version_tag`, `python_version`
- `slippage_model`, `commission_model`
- `allow_extended_hours` (default false)

### 4.2 orders.csv (required)

Minimum columns (typed):
- `order_id` (string; deterministic)
- `signal_id` (string; deterministic)
- `symbol` (string)
- `side` (LONG/SHORT or BUY/SELL but consistent)
- `order_type` (STOP/LIMIT/MARKET)
- `entry_level`
- `sl_level`, `tp_level` (nullable)
- `valid_from_ts`, `valid_to_ts` (tz-aware timestamps)
- `created_from_ts` (signal timestamp)
- `qty`
- `oco_group` (string; deterministic if used)
- `metadata_json` (optional)

### 4.3 filled_orders.csv (required when any fills occur)

Minimum columns:
- `fill_id`
- `order_id`
- `trade_id`
- `symbol`
- `fill_type` (ENTRY|EXIT)
- `fill_ts` (tz-aware)
- `fill_price`
- `fill_qty`
- `slippage`
- `commission`
- `exit_reason` (TP|SL|EOD|EXPIRED|MANUAL|UNKNOWN)
- `bar_ts_exec` (the exec bar start ts used for that fill)
- `evidence_codes` (comma list; see §6)

### 4.4 trades.csv (required)

Minimum columns:
- `trade_id`
- `order_id` (or entry order id)
- `symbol`
- `side`
- `entry_ts`, `entry_price`
- `exit_ts`, `exit_price`
- `qty`
- `pnl_gross`, `pnl_net`
- `exit_reason`
- `duration_minutes`
- `signal_tf`, `exec_tf`
- `evidence_status` (PASS|WARN|FAIL)
- `evidence_codes` (comma list)

### 4.5 equity_curve.csv (required)

Minimum columns:
- `ts` (trade close timestamps or regular step timestamps)
- `equity`
- `drawdown`
- `pnl_net_cum`

### 4.6 Bars persistence (required)

All runs must persist bars used for proof:
```
bars/bars_signal_<TF>_rth.parquet
bars/bars_exec_<TF>_rth.parquet
```

> **Invariant ART-1:** If `exec_tf` is M1, M1 exec bars must be persisted for audit ("proof").
> If M1 persistence is not available, trade evidence must be downgraded to WARN with code `NO_EXEC_BARS_M1`.

---

## 5. Deterministic IDs and Lineage

### 5.1 Deterministic IDs

IDs must be deterministic to guarantee reproducibility across machines:

- `signal_id = hash(run_id + symbol + signal_ts + side + key_levels)`
- `order_id = hash(signal_id + validity window + entry level)`
- `trade_id = hash(order_id + entry fill ts)`
- `fill_id = hash(trade_id + fill_type + fill_ts)`

> **Invariant ID-1:** IDs must be stable given identical inputs and data.

### 5.2 Lineage integrity

> **Invariant LIN-1:** Every trade must map to:
> - exactly one entry fill
> - exactly one exit fill (or an explicit EXPIRED/NO_FILL outcome)
>
> **Invariant LIN-2:** Joins between orders, fills, trades must be possible using explicit IDs (no fragile composite joins in audits).

---

## 6. Evidence Model (Proof Codes)

Define evidence codes as a stable enum-like list (do not invent ad-hoc strings in UI):

**PASS/WARN/FAIL** plus codes like:
- `RTH_OK` / `RTH_VIOLATION`
- `SIGNAL_GRID_OK` / `SIGNAL_GRID_VIOLATION`
- `EXEC_EARLIEST_TOUCH_OK` / `EXEC_EARLIEST_TOUCH_VIOLATION`
- `FILL_WITHIN_BAR_OK` / `FILL_OUTSIDE_BAR`
- `NO_EXEC_BARS_M1`
- `TZ_MIXED_DETECTED`
- `ORDER_VALIDITY_OK` / `ORDER_VALIDITY_VIOLATION`
- `LOOKAHEAD_SUSPECTED`

> **Invariant EVID-1:** Trades and fills must carry evidence codes and an `evidence_status`.

### 6.1 Implementation Status

> [!IMPORTANT]
> **Evidence Code System Status**: DESIGNED but NOT YET ENFORCED
> 
> **Current State** (as of 2026-01-02):
> - Evidence codes are defined and documented (above list is normative)
> - **Code enforcement**: Planned but not yet implemented
> - **Missing**: `EvidenceCode` enum, centralized registry, validation in run pipeline
> 
> **Until enforcement is implemented**:
> - Strategies MAY emit evidence strings but there is NO validation against this canonical list
> - Audit tools SHOULD warn on unknown evidence codes
> - **Risk**: Ad-hoc evidence strings may leak into outputs
> 
> **Acceptance Criteria for "Enforced"**:
> 1. `EvidenceCode` enum exists in `axiom_bt/contracts/evidence.py`
> 2. All evidence-emitting functions use enum values only
> 3. Validation in run pipeline rejects unknown codes
> 4. Tests verify enum completeness matches contract

---

## 7. Determinism and Auditability

### 7.1 Determinism Guarantee

> **Invariant DET-1**: No usage of `now()` or wall-clock time in simulation; time is derived from data windows and run metadata.

**Definition**: A backtest is **deterministic** if:

```
Same inputs → Same outputs

Where:
- Same inputs  = identical data files + identical config + identical code (git SHA)
- Same outputs = identical trades, fills, orders, equity curve, metrics
```

**Allowed Variances** (these MAY differ between runs):
- `run_id` (contains timestamp component)
- Execution time metrics (e.g., `runtime_seconds`, `wall_clock_start`)
- Log message timestamps
- Artifact file creation timestamps (filesystem metadata)

**MUST Match Exactly**:
| Output | Comparison Method | Tolerance |
|--------|-------------------|-----------|
| Trade timestamps | Exact match | 0 ms |
| Trade prices | Exact match | 0.0 |
| Trade quantities | Exact match | 0 |
| Order IDs, fill IDs, trade IDs | Exact match (if deterministic ID gen implemented) | - |
| Equity curve values | Exact match | 0.0 |
| Performance metrics (Sharpe, DD, win rate) | Exact match | 0.0001 (rounding) |

### 7.2 Reproducibility Test Procedure

**To verify a run is reproducible**:

1. **Record inputs**:
   ```bash
   RUN_1_ID="original_run_id"
   git rev-parse HEAD > commit_sha.txt
   cp config.yaml config_frozen.yaml
   cp -r artifacts/data_m1_rth artifacts/data_frozen
   ```

2. **Execute run 1**:
   ```python
   result_1 = run_backtest_full(...)
   # Produces: artifacts/backtests/$RUN_1_ID/
   ```

3. **Re-execute run 2 (same inputs)**:
   ```bash
   git checkout $(cat commit_sha.txt)
   export DATA_PATH=artifacts/data_frozen
   result_2 = run_backtest_full(...)  # Same params as Run 1
   ```

4. **Compare outputs**:
   ```bash
   diff <(sort $RUN_1_ID/trades.csv) <(sort $RUN_2_ID/trades.csv)
   diff <(sort $RUN_1_ID/orders.csv) <(sort $RUN_2_ID/orders.csv)
   diff $RUN_1_ID/equity_curve.csv $RUN_2_ID/equity_curve.csv
   ```

5. **Acceptance**:
   - ✅ **PASS**: All diffs empty (except run_id, timestamps)
   - ❌ **FAIL**: Any trade, order, fill, or equity value differs

### 7.3 Deterministic ID Generation (Current Status: NOT IMPLEMENTED)

**Contract Requirement**:
- `signal_id = hash(run_id + symbol + signal_ts + side + levels)`
- `order_id = hash(signal_id + validity + entry_level)`
- `trade_id = hash(order_id + entry_fill_ts)`

**When implemented**: IDs will be reproducible across machines and runs.  
**Until then**: IDs may be pandas-index or UUID-based (run-specific, not reproducible).

### 7.4 Audit Trail Requirements

> **Invariant AUD-1**: `run_steps.jsonl` must include counts for orders, fills, trades, and evidence PASS/WARN/FAIL distribution.
> **Invariant AUD-2**: All artifacts required by this contract must be listed in `run_manifest.json`.

**Audit Checklist** (for contract compliance):

- [ ] `run_meta.json` exists with: run_id, symbol, mode, timezones, git SHA, config snapshot
- [ ] `orders.csv` row count matches `run_steps.jsonl` → `orders_generated`
- [ ] `filled_orders.csv` row count matches `run_steps.jsonl` → `fills_executed`
- [ ] `trades.csv` row count matches `run_steps.jsonl` → `trades_completed`
- [ ] Evidence distribution (PASS/WARN/FAIL) matches `run_steps.jsonl`
- [ ] Bars persisted: `bars/bars_exec_M1_rth.parquet`, `bars/bars_signal_*_rth.parquet`
- [ ] `run_manifest.json` lists all artifacts with checksums

---

## 8. Contract Acceptance Criteria

A run is **contract-compliant** if:

1. All required artifacts exist (or are explicitly marked N/A by mode).
2. RTH-only enforcement passes (unless explicitly overridden).
3. Signal timestamps align to `signal_tf`.
4. Fills execute on earliest-touch on `exec_tf`.
5. Fills are price-plausible vs exec bars.
6. Deterministic IDs allow 1:1 lineage joins.
7. Evidence codes are complete and stable.

---

## 9. Required Implementation Changes (Pending Approval)

Based on current system analysis, the following implementation changes may be needed to achieve full contract compliance:

### 9.1 Artifacts Completeness

- **Verify `bars_exec_M1_rth.parquet` persistence:** Current implementation may not persist M1 exec bars consistently. If missing, implement persistence with RTH filtering applied.
- **Add `run_manifest.json`:** Currently not generated. Should list all artifact files with checksums for audit trail.

### 9.2 Deterministic ID Implementation

- **Audit current ID generation:** Verify that `signal_id`, `order_id`, `trade_id`, `fill_id` use stable hashing and include all required components.
- **If IDs are currently UUID-based:** Replace with deterministic hash-based generation as specified in §5.1.

### 9.3 Evidence Code Standardization

- **Centralize evidence code definitions:** Create an `EvidenceCode` enum or constant registry to prevent ad-hoc string usage.
- **Add evidence validation:** Implement validators that check all evidence codes against the canonical list.

### 9.4 RTH Enforcement Audit

- **Verify RTH filter application order:** Ensure RTH filtering happens in `market_tz` before any timezone conversion to `storage_tz`.
- **Add `allow_extended_hours` flag:** Currently not exposed in config; add to run metadata and enforce degraded evidence marking.

### 9.5 Hybrid Mode Validation

- **Verify single-direction enforcement:** Add validation that daily signals cannot produce both LONG and SHORT orders (Invariant HYB-1).
- **Add next-day entry enforcement:** Verify that hybrid entries only occur on D+1, never same-day (Invariant HYB-2).

> [!IMPORTANT]
> These changes require approval before implementation. They are documented here to maintain contract completeness and identify gaps between specification and current runtime behavior.

---

## 10. Appendix A: Typical Resampling Parameters (Non-normative)

### M1 → M5 Resampling
```python
{
  "base_tf": "1min",
  "target_tf": "5min",
  "label": "left",
  "closed": "left",
  "origin": "start_day"
}
```

### M5 → M15 Resampling
```python
{
  "base_tf": "5min",
  "target_tf": "15min",
  "label": "left",
  "closed": "left"
}
```

### Daily Aggregation from M1
```python
{
  "base_tf": "1min",
  "target_tf": "1D",
  "label": "left",
  "closed": "right",  # Daily bar closes at market close
  "origin": "start_day"
}
```

---

## 10. Appendix B: Example Artifacts (Non-normative)

### Example run_meta.json (excerpt)
```json
{
  "run_id": "251222_110818_IONQ_NEW1_IB_100d",
  "symbol": "IONQ",
  "mode": "HYBRID",
  "market_tz": "America/New_York",
  "storage_tz": "UTC",
  "rth_start": "09:30:00",
  "rth_end": "16:00:00",
  "rth_enforced": true,
  "allow_extended_hours": false,
  "signal_tf": "D1",
  "exec_tf": "M1",
  "daily_tf": "D1",
  "bar_label": "left",
  "bar_closed": "left",
  "git_sha": "e8d91da",
  "version_tag": "v2.2.0-trade-inspector",
  "slippage_model": "fixed_bps",
  "commission_model": "ib_tiered"
}
```

### Example orders.csv (sample rows)
```csv
order_id,signal_id,symbol,side,order_type,entry_level,sl_level,tp_level,valid_from_ts,valid_to_ts,created_from_ts,qty,oco_group
ord_a1b2c3,sig_x9y8z7,IONQ,LONG,STOP,28.50,27.00,30.00,2025-12-20T14:30:00Z,2025-12-20T21:00:00Z,2025-12-19T21:00:00Z,100,oco_grp_001
```

### Example filled_orders.csv (sample rows)
```csv
fill_id,order_id,trade_id,symbol,fill_type,fill_ts,fill_price,fill_qty,slippage,commission,exit_reason,bar_ts_exec,evidence_codes
fill_001,ord_a1b2c3,trade_001,IONQ,ENTRY,2025-12-20T14:35:00Z,28.52,100,0.02,1.00,,2025-12-20T14:35:00Z,"RTH_OK,EXEC_EARLIEST_TOUCH_OK,FILL_WITHIN_BAR_OK"
fill_002,ord_a1b2c3,trade_001,IONQ,EXIT,2025-12-20T15:42:00Z,30.01,100,0.01,1.00,TP,2025-12-20T15:42:00Z,"RTH_OK,EXEC_EARLIEST_TOUCH_OK,FILL_WITHIN_BAR_OK"
```

### Example trades.csv (sample rows)
```csv
trade_id,order_id,symbol,side,entry_ts,entry_price,exit_ts,exit_price,qty,pnl_gross,pnl_net,exit_reason,duration_minutes,signal_tf,exec_tf,evidence_status,evidence_codes
trade_001,ord_a1b2c3,IONQ,LONG,2025-12-20T14:35:00Z,28.52,2025-12-20T15:42:00Z,30.01,100,149.00,147.00,TP,67,D1,M1,PASS,"RTH_OK,SIGNAL_GRID_OK,EXEC_EARLIEST_TOUCH_OK"
```

---

**Document Version:** 1.0
**Last Updated:** 2025-12-24
**Maintaining Team:** Trading Platform Engineering
