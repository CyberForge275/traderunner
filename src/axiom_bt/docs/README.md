# axiom_bt Framework Documentation

**Last Updated:** 2024-12-24  
**Version:** 1.0

---

## Overview

This directory contains comprehensive technical documentation for the `axiom_bt` backtesting framework, covering architecture, interfaces, execution semantics, and critical implementation details.

## Documentation Index

### 📘 [Interface Specification](./axiom_bt_interface_specification.md)

**Purpose:** Canonical interface definitions for all backtesting modes

**Contents:**
- Architecture overview with component diagrams
- **Mode 1: Intraday Backtesting** (M1/M5/M15 execution)
  - Orders CSV schema
  - Entry/exit logic (`_first_touch_entry`, `_exit_after_entry`)
  - Cost application (slippage, fees)
  - RTH (Regular Trading Hours) enforcement
- **Mode 2: Daily MOC Backtesting** (Market-on-Close)
  - Current implementation limitations
  - Single-bar fill semantics
- **Mode 3: Hybrid Backtesting** (PROPOSED - not yet implemented)
  - Design specification for daily signals + intraday execution
  - Required schema extensions
  - Lookahead bias prevention strategies
- Data layer specifications (`IntradayStore`, `DailyStore`)
- Contract validation (`DailyFrameSpec`, `IntradayFrameSpec`)
- Timestamp handling and timezone conversion
- Edge cases and behavioral quirks
- Implementation recommendations

**When to read:** 
- Before implementing a new strategy
- When integrating with the backtest pipeline
- To understand execution semantics and fill logic

---

### ⚠️ [Critical Issues & Risk Analysis](./axiom_bt_risk_analysis.md)

**Purpose:** Deep-dive analysis of implementation gaps, biases, and risks

**Contents:**
- **Critical Issues**
  - ❌ Issue #1: Hybrid mode not implemented
  - ⚠️ Issue #2: Same-bar SL/TP priority bias (always exits at SL)
  - ⚠️ Issue #3: Incomplete daily MOC implementation
  - ⚠️ Issue #4: Intra-bar fill timing ambiguity
  - ⚠️ Issue #5: RTH filter inconsistency risk
  - 🔍 Issue #6: Warmup data leakage potential
- **Behavioral Quirks**
  - Zero-orders equity curve synthesis
  - OCO group break behavior
  - Slippage on stop orders
- **Timestamp & timezone handling** deep-dive
- **Data coverage & gap handling** strategies
- **Performance considerations**
- **Testing recommendations** with specific test cases
- **Code hotspots** reference table
- **Prioritized recommendations** (High/Medium/Low)

**When to read:**
- Before running production backtests
- When debugging unexpected backtest results
- To understand performance biases (conservative vs optimistic)
- When planning framework improvements

---

## Quick Start

### For Strategy Developers

1. Read [Interface Specification - Intraday Mode](./axiom_bt_interface_specification.md#mode-1-intraday-backtesting)
2. Review the **Orders CSV Schema** to understand required fields
3. Check [Entry/Exit Logic](./axiom_bt_interface_specification.md#execution-semantics) to understand fill assumptions
4. Read [Critical Issues - Same-Bar SL/TP](./axiom_bt_risk_analysis.md#-issue-2-same-bar-sltp-priority-bias) to understand conservative bias

### For Framework Maintainers

1. Review [Architecture Overview](./axiom_bt_interface_specification.md#architecture-overview)
2. Study [Critical Issues](./axiom_bt_risk_analysis.md#critical-issues) for implementation gaps
3. Consult [Recommendations](./axiom_bt_risk_analysis.md#summary-of-recommendations) for prioritized improvements
4. Reference [Code Hotspots](./axiom_bt_risk_analysis.md#quick-reference-code-hotspots) when modifying core logic

### For Auditors

1. Start with [Timestamp Handling](./axiom_bt_interface_specification.md#timestamp-handling--lookahead-bias-prevention)
2. Review [Lookahead Bias Prevention](./axiom_bt_interface_specification.md#critical-invariants-for-hybrid-mode) strategies
3. Check [RTH Enforcement](./axiom_bt_risk_analysis.md#-issue-5-rth-filter-not-applied-in-replayengine)
4. Validate against [Testing Recommendations](./axiom_bt_risk_analysis.md#testing-recommendations)

---

## Key Findings Summary

### ✅ What Works Well

| Feature | Confidence | Notes |
|---------|-----------|-------|
| Intraday execution (M1/M5/M15) | 85% | Conservative, well-tested |
| Timezone handling | 95% | Strict UTC internally, configurable display |
| RTH filtering (data layer) | 90% | Pre/post market excluded |
| Coverage gates | 85% | Validates data before execution |
| Diagnostics & artifacts | 90% | Comprehensive trade evidence |

### ❌ Critical Gaps

| Gap | Impact | Status |
|-----|--------|--------|
| Hybrid mode (daily → intraday) | HIGH | **Not implemented** |
| Daily MOC multi-day positions | MEDIUM | **Incomplete** (stub only) |
| Same-bar SL/TP bias | MEDIUM | Conservative (always SL) |
| Intra-bar fill timing | LOW | Returns bar open timestamp |

### 📊 Mode Confidence Assessment

- **Intraday Mode:** 85% - Production-ready with documented biases
- **Daily MOC Mode:** 40% - Limited to single-bar fills
- **Hybrid Mode:** 0% - Does not exist (see proposed design in specification)

---

## File References

### Core Framework Files

| File | Purpose | Lines |
|------|---------|-------|
| [`full_backtest_runner.py`](../full_backtest_runner.py) | Pipeline orchestration | 1405 |
| [`engines/replay_engine.py`](../engines/replay_engine.py) | Trade simulation | 562 |
| [`intraday.py`](../intraday.py) | M1/M5/M15 data loading | 592 |
| [`daily.py`](../daily.py) | D1 data loading | 176 |
| [`contracts/data_contracts.py`](../contracts/data_contracts.py) | OHLCV validation | 154 |
| [`contracts/order_schema.py`](../contracts/order_schema.py) | Order schema | 165 |
| [`contracts/signal_schema.py`](../contracts/signal_schema.py) | Signal schema | 108 |

### Key Functions by Concern

| Concern | Location | Description |
|---------|----------|-------------|
| Entry detection | `replay_engine.py:60-76` | `_first_touch_entry()` |
| Exit logic | `replay_engine.py:79-111` | `_exit_after_entry()` |
| Intraday backtest | `replay_engine.py:148-438` | `simulate_insidebar_from_orders()` |
| Daily backtest | `replay_engine.py:441-561` | `simulate_daily_moc_from_orders()` |
| Full pipeline | `full_backtest_runner.py:146-844` | `run_backtest_full()` |
| Warmup calculation | `full_backtest_runner.py:40-80` | `calculate_warmup_days()` |
| Coverage gate | `full_backtest_runner.py:294-330` | Coverage validation |

---

## Contributing

When updating this documentation:

1. **Keep accurate:** Update code references when implementation changes
2. **Version control:** Update "Last Updated" date at top of each document
3. **Cross-reference:** Link between documents when discussing related concepts
4. **Add examples:** Include code snippets and test cases for clarity
5. **Prioritize readability:** Use tables, diagrams, and alerts for critical information

---

## Contact & Support

For questions or clarifications:
- Review existing conversation history (see references in documents)
- Check test suite for behavioral examples: `tests/`
- Consult dashboard implementation: `trading_dashboard/`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-12-24 | Initial documentation release covering all three modes |

---

## Glossary

- **RTH:** Regular Trading Hours (09:30-16:00 ET for US markets)
- **OCO:** One-Cancels-Other order group
- **MOC:** Market-on-Close execution
- **SL:** Stop Loss
- **TP:** Take Profit
- **SSOT:** Single Source of Truth
- **Lookahead Bias:** Using future data in historical simulation (critical flaw)
- **Warmup Period:** Historical bars for indicator calculation before backtest window
- **Slippage:** Price difference between order price and fill price
- **Intra-bar:** Within a single OHLCV bar (timing ambiguity)
