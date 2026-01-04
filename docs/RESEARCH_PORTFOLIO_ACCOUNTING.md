# Portfolio Accounting Research Memo

**Date**: 2026-01-04  
**Purpose**: Survey best practices from established backtesting frameworks for portfolio accounting, order execution, and deterministic behavior.

---

## Frameworks Surveyed

1. **vectorbt** (https://vectorbt.dev)
2. **Backtrader** (https://backtrader.com)
3. **backtesting.py** (https://kernc.github.io/backtesting.py/)

---

## Key Learnings & Adoptions

### 1. Deterministic Ordering with `call_seq` (vectorbt)

**Source**: [vectorbt Portfolio Documentation](https://vectorbt.dev/api/portfolio/)

**Concept**:
- `call_seq` parameter defines execution sequence per timestep when multiple assets share cash
- When trades occur at same timestamp, execution order affects results (cash constraints, fill prices)
- vectorbt uses explicit sequence numbers to make this deterministic

**Our Adoption**:
- ✅ Implement: `seq` field in `LedgerEntry` for tie-breaking
- ✅ Ensure: Ledger sorting by `(ts, seq)` not just `ts`
- ✅ Document: When trades have identical timestamps, `seq` determines order

**Rationale**: Multi-symbol backtests in `axiom_bt` may have simultaneous exits. Without `seq`, ledger order is non-deterministic.

---

### 2. Separate Broker/Portfolio Layer (Backtrader)

**Source**: [Backtrader Broker Documentation](https://backtrader.com/docu/broker-stocks/)

**Concept**:
- `BackBroker` manages unified portfolio Cash, equity, positions  
- Separate from strategy logic
- Commission schemes are pluggable (fixed, percentage, per-share, futures-specific)
- Position tracking automatic, strategy queries broker for current cash/value

**Our Adoption**:
- ✅ Implement: `PortfolioLedger` as separate layer (already started)
- ✅ Commission tracking: fees/slippage as evidence fields
- ⚠️ **Don't adopt yet**: Full position tracking (Step 1 = cash-only dual-track)
- 📌 **Future**: Compound mode will query `ledger.current_equity()` like Backtrader's broker

---

### 3. Commission as Net Cash Impact (backtesting.py)

**Source**: [backtesting.py API Reference](https://kernc.github.io/backtesting.py/#reference)

**Concept**:
- Commission applied both on entry AND exit
- Commission reduces cash directly (part of net P/L)
- Equity curve reflects net-of-commission performance

**Our Adoption**:
- ✅ Clarify: `pnl` field in ledger = **net cash delta** (fees already deducted in replay_engine)
- ✅ Document: `fees` and `slippage` are evidence fields (total costs)
- ✅ Formula: `cash_after = cash_before + pnl` (pnl is net)

**Rationale**: Prevents double-counting. If `pnl = gross_pnl - fees - slippage`, then ledger cash update is just `+= pnl`.

---

### 4. Equity Curve as Cumulative PnL (All Frameworks)

**Common Pattern**:
- All frameworks derive equity as: `equity(t) =initial_cash + cumsum(pnl(0..t))`
- Reconstructable from trade log

**Our Adoption**:
- ✅ Implement: `PortfolioLedger.replay_from_trades(trades_df)` static method
- ✅ Enable: Post-hoc audit by reconstructing ledger from `trades.csv` (Step B)
- ✅ Parity: Replay matches `metrics.equity_from_trades()` output

---

### 5. Timestamp Normalization (Implicit in all)

**Observation**:
- Timeindex consistency crucial for multi-asset alignment
- vectorbt: all data aligned to common time index before processing
- Backtrader: data feeds aligned by timestamp internally
- backtesting.py: single-asset (no alignment needed)

**Our Adoption**:
- ✅ Require: All timestamps in ledger tz-aware (UTC normalized)
- ✅ Reject: Naive timestamps (ValueError) OR auto-convert with evidence flag
- ✅ Enforce: Normalization BEFORE monotonic comparison

**Rationale**: Mixing naive/aware timestamps causes subtle bugs in multi-TZ runs.

---

## What We **Don't** Adopt (Out of Scope)

| Feature | Framework | Why Not Now |
|:--------|:----------|:------------|
| Full position tracking | Backtrader, vectorbt | Step 1 = cash-only dual-track |
| Multi-asset portfolio rebalancing | Backtrader, vectorbt | axiom_bt focuses on single-symbol per strategy |
| Margin/leverage accounting | Backtrader | Not needed for equity backtests |
| Pluggable commission schemes | Backtrader | Fees already handled in replay_engine |
| Advanced order types (OCO, etc.) | Backtrader | Out of scope for portfolio hardening |

---

## Implementation Checklist (Cross-Reference to Steps A-D)

- [x] **Step A**: Relaxed monotonic enforcement (multi-symbol safe)
  - Inspired by: vectorbt's `call_seq` acknowledgment that same-timestamp events exist
  
- [x] **Step B**: Replay from trades (deterministic reconstruction)
  - Inspired by: All frameworks' equity = cumsum(pnl) pattern
  
- [x] **Step C**: Clarify cost semantics (pnl = net)
  - Inspired by: backtesting.py's commission-as-net-impact model
  
- [ ] **Step D**: Manifest integration (discoverability)
  - No direct parallel in surveyed frameworks (artifact management is custom)

---

## References

1. **vectorbt**: https://vectorbt.dev - High-performance vectorized backtesting
   - Key: `call_seq` for deterministic multi-asset execution
   - Docs: https://vectorbt.dev/api/portfolio/

2. **Backtrader**: https://backtrader.com - Event-driven backtesting framework
   - Key: Separate broker/portfolio layer with commission schemes
   - Docs: https://backtrader.com/docu/broker-stocks/

3. **backtesting.py**: https://kernc.github.io/backtesting.py/ - Lightweight backtesting
   - Key: Simple commission model, equity as cumulative PnL
   - GitHub: https://github.com/kernc/backtesting.py

---

*Research completed*: 2026-01-04  
*Frameworks reviewed*: 3  
*Adoptions*: 5 key learnings applied to Steps A-D
