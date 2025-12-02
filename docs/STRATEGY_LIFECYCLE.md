# Strategy Development Lifecycle

**Version**: 1.0  
**Last Updated**: 2025-12-02  
**Status**: Active Framework

---

## Overview

This document defines the **5-stage lifecycle** for developing, testing, and deploying trading strategies in our automated trading system. Each stage has specific goals, tools, and validation criteria to ensure strategies are robust before deployment to live markets.

---

## 🔬 Stage 1: Exploration Lab

**Goal**: Transform external strategy scripts into Python and validate basic logic with synthetic data.

### Activities

1. **Strategy Import & Conversion**
   - Import from PineScript (TradingView) or RealTest format
   - Convert to Python using `traderunner` framework
   - Document strategy logic, rules, and parameters

2. **Synthetic Data Testing**
   - Generate test data with known patterns
   - Verify strategy triggers on expected conditions
   - Validate entry/exit logic is implemented correctly
   - Check edge cases (gaps, halts, extreme volatility)

### Tools & Environment

- **Location**: `traderunner/src/strategies/`
- **Data Source**: Synthetic/generated test data
- **Output**: Python strategy module with unit tests
- **Runtime**: Development machine, no market connection needed

### Success Criteria

- ✅ Strategy compiles and runs without errors
- ✅ Generates expected signals on test patterns
- ✅ All unit tests pass
- ✅ Code review approved

### Exit Criteria

Strategy passes synthetic data tests and is ready for historical backtesting.

---

## 📊 Stage 2: Backtesting Lab

**Goal**: Validate strategy performance on historical market data and optimize parameters.

### Activities

1. **Historical Backtesting**
   - Run strategy against real EODHD historical data
   - Test multiple time periods (bull, bear, sideways markets)
   - Analyze performance metrics (Sharpe, drawdown, win rate)

2. **Parameter Optimization**
   - Identify key strategy parameters (filters, thresholds, lookback periods)
   - Run parameter sweeps to find optimal values
   - Validate against out-of-sample data (avoid overfitting)
   - Document final parameter configuration

3. **Robustness Testing**
   - Walk-forward analysis
   - Monte Carlo simulation
   - Transaction cost sensitivity
   - Slippage assumptions

### Tools & Environment

- **Location**: `traderunner/backtests/`
- **Data Source**: EODHD historical data (daily/intraday)
- **Output**: Backtest reports, parameter studies, performance metrics
- **Runtime**: Development machine or dedicated backtest server

### Success Criteria

- ✅ Positive risk-adjusted returns (Sharpe > 1.0)
- ✅ Acceptable maximum drawdown (< 20%)
- ✅ Win rate meets minimum threshold (strategy-dependent)
- ✅ Performance stable across multiple time periods
- ✅ Parameters validated out-of-sample

### Exit Criteria

Strategy demonstrates profitable performance on historical data with acceptable risk metrics.

---

## 🔍 Stage 3: Pre-PaperTrade Lab

**Goal**: Validate strategy execution with live market data (ticks) without placing orders.

### Activities

1. **Live Data Validation**
   - Connect `marketdata-stream` to EODHD real-time feed
   - Verify strategy receives and processes tick data correctly
   - Confirm signal generation timing (latency, delays)

2. **Signal Logic Verification**
   - Monitor generated signals in real-time
   - Cross-check signals against expected behavior
   - Validate entry/exit triggers fire correctly
   - Confirm idempotency and duplicate prevention

3. **Dry-Run Order Generation**
   - Generate order intents (stored in `signals.db`)
   - Do NOT submit to `automatictrader-api`
   - Log would-be orders for analysis
   - Review signal quality and false positives

### Tools & Environment

- **Location**: `marketdata-stream` with strategy module
- **Data Source**: EODHD real-time WebSocket (live ticks)
- **Output**: Signal log, analysis reports
- **Runtime**: Server or development machine during market hours
- **Mode**: Read-only, no order submission

### Success Criteria

- ✅ Strategy processes live ticks without errors
- ✅ Signals trigger as expected based on backtest logic
- ✅ No unexpected signals or false triggers
- ✅ Latency acceptable (< 100ms from tick to signal)
- ✅ Signal quality meets expectations (manual review)

### Exit Criteria

Strategy proven to work correctly with live market data; ready for paper trading.

---

## 📝 Stage 4: PaperTrade

**Goal**: Execute full trading workflow with paper account during market hours.

### Activities

1. **Paper Account Setup**
   - Configure Interactive Brokers paper trading account
   - Set up `automatictrader-worker` in `paper-send` mode
   - Configure risk limits (position size, daily loss, concentration)

2. **Live Paper Trading**
   - Run complete signal → intent → order flow
   - Execute orders in IB paper account
   - Monitor fills, slippage, and execution quality
   - Track P&L and performance metrics

3. **Operational Validation**
   - Test during various market conditions (open, close, volatile periods)
   - Verify risk management (kill switch, position limits)
   - Confirm error handling (TWS disconnect, API failures)
   - Validate monitoring and alerting

### Tools & Environment

- **Services**: All 3 services running (`marketdata-stream`, `automatictrader-api`, `traderunner`)
- **Data Source**: EODHD live ticks
- **Broker**: Interactive Brokers Paper Trading Account
- **Output**: Trade log, P&L reports, performance dashboard
- **Runtime**: Production server during market hours (9:30-16:00 ET)
- **Mode**: Full execution, paper money only

### Success Criteria

- ✅ Signals convert to orders successfully (> 95% success rate)
- ✅ Orders execute in IB paper account
- ✅ Fills match expectations (slippage < 0.1%)
- ✅ Risk limits enforced correctly
- ✅ No system errors or crashes
- ✅ Performance tracks backtest projections (within reason)
- ✅ Monitoring alerts work correctly

### Exit Criteria

Strategy executes flawlessly in paper trading for **minimum 2 weeks** (10 trading days) with acceptable performance and zero critical errors.

---

## 💰 Stage 5: AutomaticTrader (Live Production)

**Goal**: Deploy strategy to live production with real capital.

### Activities

1. **Production Deployment**
   - Configure Interactive Brokers live trading account
   - Set conservative risk limits for initial deployment
   - Start with small position sizes (10-20% of target)
   - Enable all monitoring and alerting

2. **Gradual Scale-Up**
   - Week 1-2: 10-20% position sizing
   - Week 3-4: 50% position sizing
   - Month 2+: 100% position sizing (if performance acceptable)

3. **Continuous Monitoring**
   - Daily performance review
   - Weekly parameter validation
   - Monthly comprehensive analysis
   - Quarterly strategy re-evaluation

4. **Risk Management**
   - Strict adherence to kill switch rules
   - Position size limits enforced
   - Drawdown protection active
   - Manual override capability maintained

### Tools & Environment

- **Services**: All 3 services (containerized with Docker recommended)
- **Data Source**: EODHD live ticks
- **Broker**: Interactive Brokers Live Trading Account
- **Output**: Trade log, P&L reports, risk metrics, compliance reports
- **Runtime**: Production server (24/7 monitoring, trading during market hours)
- **Mode**: Live execution, real capital

### Success Criteria

- ✅ Strategy executing as designed
- ✅ Performance within expected range
- ✅ Risk limits never breached
- ✅ No unplanned downtime
- ✅ All monitoring functioning
- ✅ Profitability measured over time

### Deactivation Criteria (Emergency)

Strategy will be **immediately deactivated** if:
- ❌ Kill switch triggered (daily loss limit)
- ❌ Unexpected behavior or bugs discovered
- ❌ Performance significantly worse than backtest
- ❌ Risk limit breached multiple times
- ❌ Market conditions fundamentally change

---

## 📋 Stage Transition Checklist

Use this checklist when promoting a strategy to the next stage:

### Exploration → Backtesting
- [ ] All unit tests passing
- [ ] Strategy logic validated on synthetic data
- [ ] Code reviewed and approved
- [ ] Documentation complete

### Backtesting → Pre-PaperTrade
- [ ] Backtest results reviewed and approved
- [ ] Parameter optimization complete
- [ ] Out-of-sample validation successful
- [ ] Risk metrics acceptable

### Pre-PaperTrade → PaperTrade
- [ ] Live tick processing verified
- [ ] Signal generation validated
- [ ] No false positives observed
- [ ] Latency acceptable

### PaperTrade → AutomaticTrader
- [ ] 10+ days successful paper trading
- [ ] Zero critical errors
- [ ] Risk limits tested and working
- [ ] Performance meets expectations
- [ ] Team approval obtained
- [ ] Capital allocated

---

## 🔄 Continuous Improvement

Strategies in production should be:
- **Re-backtested** quarterly with latest data
- **Re-optimized** if performance degrades
- **Evaluated** for retirement if no longer profitable
- **Enhanced** based on market feedback and analysis

---

## 📁 Directory Structure

Organize strategies according to their lifecycle stage:

```
traderunner/
├─ src/
│  ├─ strategies/
│  │  ├─ exploration/       # Stage 1: Under development
│  │  ├─ backtesting/       # Stage 2: Being validated
│  │  ├─ pre_papertrade/    # Stage 3: Live data validation
│  │  ├─ papertrade/        # Stage 4: Paper trading
│  │  └─ production/        # Stage 5: Live trading
│  └─ ...
└─ ...
```

---

## 🎯 Key Principles

1. **Never skip stages** - Each stage validates different aspects
2. **Document everything** - Decisions, parameters, results
3. **Conservative approach** - Start small, scale gradually
4. **Risk first** - Always prioritize capital preservation
5. **Continuous validation** - Monitor and adjust constantly

---

## 📊 Metrics & KPIs by Stage

| Stage | Key Metrics |
|-------|-------------|
| **Exploration** | Compile success, test coverage |
| **Backtesting** | Sharpe ratio, max drawdown, win rate |
| **Pre-PaperTrade** | Signal accuracy, latency, false positives |
| **PaperTrade** | Execution rate, slippage, system uptime |
| **AutomaticTrader** | Realized P&L, risk-adjusted returns, Calmar ratio |

---

## 🚨 Important Notes

- **Backtest results DO NOT guarantee live performance**
- **Market conditions change** - strategies must adapt
- **Risk management is paramount** - protect capital first
- **Paper trading is critical** - don't skip it
- **Start small** - scale up only after proven success

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-02 | Initial framework definition |

---

**For questions or clarifications, refer to**:
- Backtest framework: `traderunner/docs/BACKTESTING_GUIDE.md`
- Risk management: `automatictrader-api/docs/RISK_MANAGEMENT.md`
- Production deployment: `docs/DEPLOYMENT.md`
