# Backtesting System - Handover Documentation

## Quick Links

**Workspace:** `/home/mirko/data/workspace/droid/traderunner`  
**Streamlit UI:** `streamlit run apps/streamlit/app.py`  
**Successful Run:** `artifacts/backtests/run_20251127_120221_ui_m5_APP_360d_10k`

---

## Current System Architecture

### Projects (all in `/home/mirko/data/workspace/droid/`)

```
traderunner/                    # Main backtesting & strategy framework
├── apps/streamlit/app.py      # Backtesting UI
├── src/
│   ├── backtest/              # Backtesting engine
│   ├── signals/               # Strategy implementations
│   ├── replay/                # Time Machine (NEW)
│   └── strategies/            # Inside Bar, Rudometkin MOC
├── artifacts/backtests/       # Backtest results
└── data/                      # Historical data (Parquet files)

marketdata-stream/              # Live data ingestion (Server: 192.168.178.55)
├── data/signals.db            # Signal database
└── config/strategy_params.yaml

automatictrader-api/            # Order execution layer (Server: 192.168.178.55)
└── data/automatictrader.db    # Trading database
```

---

## Backtesting Infrastructure

### Successful Run Example

**Run ID:** `run_20251127_120221_ui_m5_APP_360d_10k`

**Results:**
- Symbol: APP
- Period: 360 days (Dec 2024 - Nov 2025)
- Timeframe: M5 (5-minute candles)
- Trades: 411
- Profit: $17,009
- Sharpe Ratio: 5.8
- Win Rate: 62%
- Strategy: InsideBar

**Output Files:**
```
artifacts/backtests/run_20251127_120221_ui_m5_APP_360d_10k/
├── orders.csv          # All order entries/exits
├── trades.csv          # Completed trades with PnL
├── filled_orders.csv   # Execution details
├── metrics.json        # Performance metrics
├── equity_curve.csv    # Equity progression
└── *.png              # Charts (equity, drawdown)
```

### Streamlit Backtesting UI

**Location:** `apps/streamlit/app.py`

**Features:**
- Strategy selection (InsideBar, Rudometkin MOC)
- Symbol picker from universe
- Date range selection
- Parameter tuning (ATR, Risk/Reward, etc.)
- Real-time visualization
- Export to CSV/Parquet

**To Run:**
```bash
cd ~/data/workspace/droid/traderunner
source .venv/bin/activate
streamlit run apps/streamlit/app.py
```

**Access:** http://localhost:8501

---

## Time Machine Replay Tool (NEW)

**Purpose:** Inject historical successful backtest signals into Pre-Papertrading Lab for pipeline testing

**Location:** `src/replay/time_machine.py`

**Usage:**
```bash
# Analyze available signals
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --analyze

# Inject specific date
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --date 2024-12-04

# Rollback
python src/replay/time_machine.py --rollback
```

**Features:**
- Automatic backup before injection
- Schema auto-detection
- Duplicate prevention
- One-command rollback

**Docs:** `src/replay/README.md`

---

## Strategies Available

### 1. InsideBar Strategy

**Source:** `src/strategies/inside_bar.py`  
**Config:** `marketdata-stream/config/strategy_params.yaml`

**Entry:** Breakout above/below mother candle  
**Exit:** Take-profit (R:R based) or stop-loss  
**Timeframes:** M5, M15, H1

**Key Parameters:**
- `risk_reward_ratio`: 1.5 - 3.0
- `stop_buffer`: ATR-based
- `take_profit_buffer`: ATR-based

### 2. Rudometkin MOC (Momentum on Close)

**Source:** `src/strategies/rudometkin_moc.py`

**Entry:** Close momentum triggers  
**Exit:** Similar to InsideBar  
**Best on:** Volatile stocks

---

## Data

### Historical Data Storage

**Location:** `traderunner/data/`  
**Format:** Parquet files  
**Symbols:** HOOD, PLTR, APP, INTC, TSLA, NVDA, MU, AVGO, LRCX, WBD  
**Timeframes:** M1, M5, M15, H1

### Data Sources

1. **EODHD API** (marketdata-stream live)
2. **Parquet archives** (traderunner backtests)

---

## Key Configuration

### Strategy Parameters

File: `marketdata-stream/config/strategy_params.yaml`

```yaml
strategies:
  insidebar:
    enabled: true
    interval: 5min
    min_mother_size: 0.5
    risk_reward_ratio: 2.0
    stop_buffer: 1.5
    take_profit_buffer: 2.0
```

### Symbols Watchlist

ENV Variable or File: `marketdata-stream/.env`

```bash
EODHD_SYMBOLS=HOOD,PLTR,APP,INTC,TSLA,NVDA,MU,AVGO,LRCX,WBD
```

---

## Testing & Validation

### Local Testing
```bash
cd ~/data/workspace/droid/traderunner
source .venv/bin/activate
pytest trading_dashboard/tests/test_dashboard.py -v
```

### Integration with Pre-Papertrading Lab

1. Use Time Machine to inject signals
2. Monitor `signals.db` → `automatictrader-api`
3. Check order intent creation in `trading.db`
4. View activity in Dashboard: http://192.168.178.55:9001

---

## Known Issues & Considerations

### ✅ Resolved
- Market-aware timestamps (US hours: 15:30-22:00 CET)
- Consistent closing prices across timeframes
- Symbol loading from environment variables
- Dashboard auto-refresh (only on Live Monitor tab)

### ⚠️ Current Limitations
- Mock data for M5 candles (not real historical data yet)
- Backtesting runs locally only
- No automated parameter optimization
- Limited to 2 strategies (InsideBar, Rudometkin MOC)

---

## Next Steps for Backtesting Improvements

### 1. Data Quality
- [ ] Integrate real M5 historical data (EODHD API)
- [ ] Validate data completeness
- [ ] Handle gaps and missing candles

### 2. Strategy Enhancements
- [ ] Parameter optimization (grid search, genetic algo)
- [ ] Walk-forward analysis
- [ ] Out-of-sample testing
- [ ] Multi-timeframe confirmation

### 3. Performance Analysis
- [ ] Risk metrics (Max DD, Sharpe, Sortino, Calmar)
- [ ] Trade distribution analysis
- [ ] Slippage & commission modeling
- [ ] Position sizing strategies

### 4. Backtesting Engine
- [ ] Portfolio-level backtesting (multiple symbols)
- [ ] Event-driven architecture
- [ ] Custom indicators framework
- [ ] Strategy combiner/ensemble

### 5. Automation
- [ ] Scheduled backtest runs
- [ ] Regression testing on strategy changes
- [ ] Performance comparison reports
- [ ] Alert on metric degradation

---

## How to Start New Backtesting Session

### For a New Agent/Conversation:

**Context to Provide:**
1. "I'm working on the traderunner backtesting system"
2. "See handover doc: `src/replay/BACKTESTING_HANDOVER.md`"
3. "Focus on: [specific improvement area]"

**Example Prompt:**
```
I need help improving the backtesting system in ~/data/workspace/droid/traderunner.
Please review src/replay/BACKTESTING_HANDOVER.md for context.

Goal: Implement parameter optimization for InsideBar strategy using grid search.
Start by analyzing the current strategy implementation and propose improvements.
```

**Key Files to Mention:**
- This handover doc
- Successful run: `artifacts/backtests/run_20251127_120221_ui_m5_APP_360d_10k`
- Strategy params: `marketdata-stream/config/strategy_params.yaml`

---

## Quick Commands Reference

```bash
# Start Streamlit UI
streamlit run apps/streamlit/app.py

# Run backtest CLI (if available)
python -m src.backtest.run_backtest --symbol APP --start 2024-01-01 --end 2024-12-31

# Analyze past run
python -c "
import pandas as pd
trades = pd.read_csv('artifacts/backtests/run_20251127_120221_ui_m5_APP_360d_10k/trades.csv')
print(trades.describe())
"

# Time Machine replay
python src/replay/time_machine.py --run-id run_20251127_120221_ui_m5_APP_360d_10k --date 2024-12-04

# Test infrastructure
pytest trading_dashboard/tests/ -v
```

---

**Document Version:** 1.0  
**Last Updated:** 2025-12-06  
**Contact:** See conversation fc7048c2-45ea-4ac3-b01e-608952bc074b for full context
