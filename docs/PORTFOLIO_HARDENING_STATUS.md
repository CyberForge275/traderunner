# Portfolio Hardening Status Report

**Date**: 2026-01-04  
**Scope**: `src/axiom_bt/portfolio/*`  
**Current State**: Step 1 dual-track completed, hardening phase initiated

---

## 1. What Is Currently Implemented

### Core Components (427 lines)

**A) `ledger.py` (281 lines)**
- ✅ `PortfolioLedger` class with dual-track accounting
- ✅ `LedgerEntry` dataclass with full evidence trail
- ✅ START entry created on initialization
- ✅ Sequence numbers (`seq`) for deterministic ordering
- ✅ cash_before/after, equity_before/after fields
- ✅ Optional monotonic timestamp enforcement (`enforce_monotonic: bool = True`)
- ✅ Timestamp handling: naive → tz_localize("UTC") in `LedgerEntry.__post_init__`
- ✅ `summary()` method for stats export

**B) `reporting.py` (143 lines)**
- ✅ Flag-gated artifacts: `AXIOM_BT_PORTFOLIO_REPORT=1`
- ✅ Generates 3 files:
  - `portfolio_ledger.csv`
  - `portfolio_summary.json`
  - `portfolio_report.md`
- ✅ Silent skip if flag not set (no default behavior change)

**C) `__init__.py`**
- Exports: `PortfolioLedger`, `LedgerEntry`

### Integration Points

**D) `replay_engine.py`**
- Line 10: `from axiom_bt.portfolio.ledger import PortfolioLedger`
- Line 316: `ledger = PortfolioLedger(initial_cash, start_ts=start_ts)`
  - `start_ts` derived from `ib_orders["valid_from"].min()` or `pd.Timestamp.now(tz=tz)`
  - **Default**: `enforce_monotonic=True` (implicit)
- Line 586: Similar initialization in `simulate_orders()` (MOC mode)
- Lines 370-383: `ledger.apply_trade()` after `cash += pnl`
- Optional parity check: `AXIOM_BT_LEDGER_PARITY=1` → asserts `abs(ledger.cash - cash) < 1e-6`

### Test Coverage

**E) `tests/test_portfolio_ledger_hardening.py` (197 lines)**
- ✅ 8 tests, all passing
- Coverage:
  - START entry existence
  - Monotonic + seq ordering
  - Rejection of backward timestamps (when enforce_monotonic=True)
  - Same timestamp handling (seq disambiguates)
  - Accounting correctness (final_cash = initial + pnl)
  - cash_before/after evidence
  - summary() stats
  - to_frame() DataFrame export

---

## 2. Identified Risks

### A) **Monotonic Enforcement Too Strict** (HIGH)
- **Issue**: Default `enforce_monotonic=True` will crash on multi-symbol backtests if trades arrive out-of-order
- **Scenario**: Symbol A exits at 10:05, Symbol B exits at 10:03 → ValueError
- **Current State**: Engine uses default=True, no override mechanism
- **Impact**: Multi-symbol runs may fail unexpectedly

### B) **Timestamp Normalization Inconsistent** (MEDIUM)
- **Issue**: `LedgerEntry.__post_init__` silently localizes naive timestamps to UTC
- **Risk**: Mixing tz-aware and naive timestamps leads to subtle bugs
- **Example**: `start_ts` from engine could be naive, gets auto-UTC'd, but order timestamps might already be in America/New_York
- **Impact**: Timestamp comparisons may be incorrect if not all normalized to same TZ

### C) **No Replay from Trades** (MEDIUM)
- **Issue**: Reporting generates ledger from live dual-track, but no way to reconstruct from `trades.csv`
- **Risk**: Cannot audit/verify ledger post-hoc
- **Use Case**: Load trades from old run → replay ledger → compare
- **Impact**: Limited forensic capability

### D) **Cost Semantics Unclear** (LOW-MEDIUM)
- **Issue**: Docs don't clarify if `pnl` is gross or net (fees already deducted?)
- **Current Code**: `cash += pnl` (line 186 in ledger.py), but fees/slippage also tracked separately
- **Risk**: Double-counting or misinterpretation in reports
- **Evidence**: `fees` and `slippage` fields exist but not used in cash calculation

### E) **Reporting Not Integrated with Manifest** (LOW)
- **Issue**: Optional artifacts not listed in `run_manifest.json`
- **Impact**: Dashboard/tooling can't discover portfolio reports
- **Current**: Files exist but "invisible" to artifact index

### F) **Sort Stability in Reporting** (LOW)
- **Issue**: `to_frame()` sorts by `[ts, seq]` but trades_df input to reporting may not be sorted
- **Risk**: Non-deterministic output if trades_df order varies
- **Impact**: Minor - mostly affects visual presentation

---

## 3. What We Will Change (Steps A-D)

### **Step A: Monotonic Safety** (Prevent Crashes)
**Goal**: Make dual-track safe for multi-symbol backtests

**Changes**:
1. Default `enforce_monotonic=False` in engine initialization
2. Add explicit parameter passing: `PortfolioLedger(..., enforce_monotonic=False)`
3. Document when strict mode is appropriate (single-symbol, debug mode)
4. Tighten timestamp normalization:
   - Require tz-aware timestamps (raise ValueError on naive)
   - OR: document that naive → UTC is auto-applied (but log warning)

**Tests**:
- Multi-symbol out-of-order scenario (no crash with enforce_monotonic=False)
- Naive timestamp handling (ValueError or logged warning)

**Deliverable**: Small commit, no behavior change for existing single-symbol runs

---

### **Step B: Replay from Trades** (Auditability)
**Goal**: Enable post-hoc ledger reconstruction

**Changes**:
1. Add `PortfolioLedger.replay_from_trades(trades_df, initial_cash, start_ts=None)` static method OR
2. Add `portfolio.reporting.replay_ledger_from_trades(...)` helper function
3. Deterministic sort key for trades:
   - Primary: `exit_ts` (UTC-normalized)
   - Tie-break: stable via `(exit_ts, symbol, side, entry_ts)` tuple
4. Replay logic:
   - Create ledger with START entry
   - For each trade (sorted): `ledger.apply_trade(exit_ts, pnl, fees, slippage)`
   - Return ledger

**Tests**:
- Determinism: same trades_df (different row order) → same ledger
- Parity: replay ledger matches metrics.equity_from_trades() output (within 1e-9)

**Deliverable**: Commit with replay function + tests

---

### **Step C: Cost Semantics Clarification** (Documentation)
**Goal**: No ambiguity about fees/slippage/pnl relationship

**Changes**:
1. Document in `ledger.py` docstring:
   - `pnl` = net cash delta (fees already deducted in current replay_engine logic)
   - `fees` and `slippage` = evidence fields (total costs for this trade)
   - Formula: `cash_after = cash_before + pnl` (pnl is net)
2. Rename fields in reports for clarity:
   - `total_fees_usd` (instead of `total_fees`)
   - `total_slippage_usd`
   - `pnl_net_usd` or `cash_delta_usd`
3. Add accounting assertion test:
   - `ledger.final_cash == ledger.initial_cash + sum(all pnl entries)`

**Tests**:
- Accounting consistency test (no double-counting)

**Deliverable**: Doc updates + report field renaming

---

### **Step D: Manifest Integration** (Discoverability)
**Goal**: Optional artifacts visible in manifest when flag active

**Changes**:
1. Modify reporting module:
   - If artifacts generated, return list of file paths
   - Caller (engine or runner) appends to manifest's `artifacts` section
2. Conditional manifest update:
   - If `AXIOM_BT_PORTFOLIO_REPORT !=1`: no manifest change (golden test passes)
   - If `=1`: manifest includes portfolio_ledger.csv, portfolio_summary.json, portfolio_report.md

**Tests**:
- Golden test: default run → manifest unchanged
- Flag test: reporting run → manifest has 3 new entries

**Deliverable**: Small manifest integration commit

---

## 4. Checkpoint: Current Guardrails Status

| Guardrail | Status |
|:----------|:-------|
| Default Runs Unchanged | ✅ Dual-track mirrors existing cash logic |
| New Artifacts Flag-Gated | ✅ `AXIOM_BT_PORTFOLIO_REPORT=1` required |
| Capsulation | ✅ Changes in `portfolio/*`, minimal hooks |
| Deterministic | ⚠️ Needs replay function + stable sort |
| Mini-Steps | ✅ Each step = small commit + tests |

---

## 5. Next Steps Outline

1. **Step 0 (This Doc)**: Status review ✅
2. **Step A**: Monotonic safety + timestamp normalization
3. **Step B**: Replay from trades + deterministic sort
4. **Step C**: Cost semantics docs + report standardization
5. **Step D**: Manifest integration (optional artifacts)
6. **Research Memo**: Internet research on portfolio accounting patterns

---

## 6. Outstanding Questions

| Question | Answer / To Be Determined |
|:---------|:--------------------------|
| Should naive timestamps be allowed? | **Decision needed**: ValueError vs auto-UTC + warning |
| Multi-symbol: always enforce_monotonic=False? | **Proposed**: Yes, unless explicit strict_time_mode flag |
| Replay function location? | **Proposed**: Static method in PortfolioLedger |
| Manifest update mechanism? | **Proposed**: Conditional append in replay_engine after reporting call |

---

*Status Document Created*: 2026-01-04  
*Current Commit*: `f5e72cf`  
*Lines of Code*: 427 (portfolio module)  
*Test Coverage*: 8 tests passing
