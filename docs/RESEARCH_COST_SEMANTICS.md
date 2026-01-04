# Cost Semantics Research Memo

**Date**: 2026-01-04  
**Purpose**: Survey best practices for commission/slippage accounting and PnL semantics from established frameworks.

---

## Key Learnings from Industry Best Practices

### 1. **Net PnL vs Gross PnL** (Universal Standard)

**Sources**: [Investopedia](https://www.investopedia.com/ask/answers/032715/what-difference-between-gross-profit-net-profit-and-operating-profit.asp), [Revolut Trading Glossary](https://www.revolut.com/en-US/help/wealth/stocks/buying-and-selling-securities/what-is-gross-profit-and-net-profit/)

**Definition**:
- **Gross PnL**: Profit before costs (price difference only)
- **Net PnL**: Profit after all costs (commissions, fees, slippage, taxes)

**Adoption**:
- ✅ **axiom_bt uses Net PnL**: `pnl` field in trades = cash delta after costs
- ✅ `fees` and `slippage` are evidence-only (not re-deducted from cash)
- ✅ Formula: `cash_after = cash_before + pnl_net`

---

### 2. **Commission Reduces Cash Directly** (Backtrader, backtesting.py)

**Sources**: [QuantInsti Backtesting Guide](https://www.quantinsti.com/blog/backtesting-trading-strategy), [QuantStart Commission Tutorial](https://www.quantstart.com/articles/Commissions-and-Slippage-in-Automated-Algorithmic-Trading/)

**Concept**:
- Commissions are deducted from account cash at trade execution
- Not a separate "cost bucket" - direct cash impact
- Both entry AND exit commissions affect final PnL

**Adoption**:
- ✅ axiom_bt: Engine calculates `pnl -= total_fees` before `cash += pnl`
- ✅ Ledger mirrors this: `fees` field is evidence, not re-applied
- ✅ Reporting must clarify: fees already baked into `pnl_net`

---

### 3. **Slippage Modeling Challenges** (QuantInsti, Exegy)

**Sources**: [QuantInsti Slippage](https://www.quantinsti.com/blog/slippage-transaction-cost-analysis), [Exegy Slippage Whitepaper](https://www.exegy.com/what-is-slippage/)

**Common Approaches**:
- Percentage-based (e.g., 0.05% of fill price)
- Dynamic (volatility-based)
- Order book simulation (advanced)

**Adoption**:
- ✅ axiom_bt: Slippage already in `fill_price` calculation (engine)
- ✅ `slippage` field = evidence (difference between expected vs actual price)
- ⚠️ **Not re-applied** in ledger cash logic

---

### 4. **Realistic Cost Estimation** (YouTube, AfterPullback)

**Sources**: [Backtesting Best Practices](https://www.afterpullback.com/backtesting-best-practices/), Trading Tutorials

**Guidance**:
- Slightly overestimate costs in backtesting (conservative approach)
- Match costs to actual broker/market (e.g., futures vs stocks)
- Include ALL fees (exchange, regulatory, clearing)

**Adoption**:
- ✅ axiom_bt: Costs configurable per engine run
- 📌 Reporting should show: `total_fees_usd`, `total_slippage_usd` for audit
- 📌 Labels: `_usd` suffix for clarity

---

### 5. **Report Field Naming Conventions** (Industry Standard)

**Observation**:
- Professional platforms use `_usd`, `_bps`, `_pct` suffixes
- Distinguish `net` vs `gross` explicitly
- Separate realized vs unrealized PnL

**Adoption**:
- ✅ Standardize reporting fields:
  - `pnl_net_usd` (or `cash_delta_usd`)
  - `total_fees_usd`
  - `total_slippage_usd`
  - `final_cash_usd`
  - `peak_equity_usd`

---

## Summary: What axiom_bt Already Does Right

| Aspect | Status |
|:-------|:-------|
| PnL = net cash delta | ✅ Correct (fees already deducted) |
| Commission direct cash impact | ✅ Matches industry standard |
| Slippage in fill price | ✅ Correct modeling |
| Fees/slippage as evidence | ✅ Good for audit |

---

## What We Need to Clarify (Step C)

1. **Docstring clarity**: Explicitly state `pnl = net cash delta`
2. **Report field naming**: Use `_usd` suffix, `net` vs `gross` labels
3. **No double-counting assertion**: `final_cash = initial + sum(pnl_net)`

---

## References

1. **QuantInsti**: https://www.quantinsti.com/blog/backtesting-trading-strategy - Comprehensive backtesting guide
2. **QuantStart**: https://www.quantstart.com/articles/Commissions-and-Slippage-in-Automated-Algorithmic-Trading/ - Commission modeling
3. **Investopedia**: https://www.investopedia.com/ask/answers/032715/what-difference-between-gross-profit-net-profit-and-operating-profit.asp - Net vs Gross definitions
4. **AfterPullback**: https://www.afterpullback.com/backtesting-best-practices/ - Realistic cost estimation
5. **Exegy**: https://www.exegy.com/what-is-slippage/ - Slippage mechanics

---

*Research completed*: 2026-01-04  
*Frameworks reviewed*: Industry best practices  
*Key insight*: axiom_bt already uses Net PnL correctly - just needs clearer documentation
