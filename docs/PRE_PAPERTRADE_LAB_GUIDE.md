# Pre-PaperTrade Lab - Quick Start Guide

## Overview

The **Pre-PaperTrade Lab** is a testing environment for strategies before moving to paper trading. It allows you to:
- **Replay historical data** to test signal generation
- **Validate the pipeline** from signals → order intents
- **Test strategies** without risking capital

---

## How to Use

### 1. Open Dashboard

```bash
cd /home/mirko/data/workspace/droid/traderunner
PYTHONPATH=$PWD python3 trading_dashboard/app.py
```

Navigate to: **http://localhost:9001**

### 2. Select Pre-PaperTrade Lab Tab

Click on the **"Pre-PaperTrade Lab"** tab in the navigation.

### 3. Configure Test

**Mode:** Currently only `Replay` mode is available (Live mode coming soon)

**Replay Configuration:**
- **Single Day:** Test specific trading day (recommended for initial testing)
- **Date Range:** Test across multiple days

**Strategy:**
- **Inside Bar** - Breakout strategy
- **Rudometkin MOC** - Market on close strategy

**Symbols:** Comma-separated list (e.g., `AAPL,TSLA,NVDA`)

**Timeframe:**
- M1, M5, M15 for intraday strategies
- D for daily strategies

### 4. Run Test

Click **"▶ Run Test"** button

The system will:
1. Load historical OHLCV data
2. Run strategy detection logic
3. Generate signals
4. Write signals to `signals.db`

### 5. Review Results

**Statistics Cards:**
- Total Signals
- BUY Signals (green)
- SELL Signals (red)

**Signals Table:**
- Symbol, Side, Entry Price
- Stop Loss, Take Profit
- Detection timestamp

### 6. Clear Test Data

Click **"🗑️ Clear Test Signals"** to remove test signals from database

---

## Architecture

### Components Created

```
trading_dashboard/
├── services/
│   └── pre_papertrade_adapter.py    # Business logic
├── repositories/
│   └── pre_papertrade.py            # Database access
├── layouts/
│   └── pre_papertrade.py            # UI layout
└── callbacks/
    └── pre_papertrade_callbacks.py  # Event handlers
```

### Pattern: Same as Backtests Tab

✅ Service Layer - `pre_papertrade_adapter.py`
✅ Repository Layer - `pre_papertrade.py`
✅ Layout Layer - `pre_papertrade.py`
✅ Callbacks Layer - `pre_papertrade_callbacks.py`
✅ Integration - `app.py` (tab registration)

---

## Signal Flow

```
┌─────────────────────────────────────┐
│   Pre-PaperTrade Lab Dashboard      │
│   (User selects strategy & date)    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   PrePaperTradeAdapter               │
│   • Loads historical data            │
│   • Runs strategy detection          │
│   • Generates signals                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   signals.db                         │
│   • Stores generated signals         │
│   • Source: pre_papertrade_replay    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   sqlite_bridge.py (if running)      │
│   • Forwards to automatictrader-api  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   automatictrader-worker             │
│   • Creates order intents            │
│   • Status: "planned"                │
└─────────────────────────────────────┘
```

---

## Example Workflow

### Test InsideBar Strategy for Yesterday

1. Select **Replay Mode** → **Single Day**
2. Set date to yesterday
3. Select **Inside Bar** strategy
4. Enter symbols: `AAPL,TSLA,NVDA`
5. Select **M5** timeframe
6. Click **Run Test**
7. Review generated signals
8. (Optional) Check if signals appear in `automatictrader-api`

### Compare Multiple Days

1. Select **Replay Mode** → **Date Range**
2. Set start/end dates (e.g., last week)
3. Run test
4. Compare signal counts across different days

---

## Future Enhancements

### Phase 2: Live Mode (Coming Soon)
- Connect to `marketdata-stream`
- Real-time signal generation
- Live pipeline testing

### Phase 3: Enhanced Features
- Signal comparison with backtests
- Performance metrics
- Signal quality analysis
- Strategy parameter optimization

---

## Troubleshooting

### No signals generated
- **Check:** Historical data exists in `artifacts/data_m5/` (or respective timeframe)
- **Solution:** Run data fetch first or use backtest pipeline

### Import errors
- **Check:** PYTHONPATH includes traderunner directory
- **Solution:** `export PYTHONPATH=/home/mirko/data/workspace/droid/traderunner:$PYTHONPATH`

### Signals not appearing in automatictrader-api
- **Check:** Is `sqlite_bridge.py` running?
- **Check:** Is `automatictrader-worker` running?
- **Solution:** Start required services on Debian server

---

## Next Steps

After successful testing in Pre-PaperTrade Lab:
1. ✅ Signals match expectations → Proceed to Paper Trading
2. ⚠️ Signals need tuning → Adjust strategy parameters
3. ❌ Issues found → Return to Backtesting Lab

---

**Status:** ✅ Ready to use
**Version:** v2.0.0-beta.2+
**Last Updated:** 2025-12-09
