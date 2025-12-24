# Paper Trading Quick Start Guide

> **Last Updated**: 2025-12-05  
> **Server**: 192.168.178.55  
> **API Port**: 8080 | **Marketdata Port**: 8090

This guide helps you set up and test the paper trading integration between `traderunner` and `automatictrader-api`.

## Prerequisites

- ✅ `marketdata-stream` running with signal generation
- ✅ `automatictrader-api` deployed to `/opt/trading/automatictrader-api`
- ✅ IB Paper Trading account (TWS on laptop: 192.168.178.54:4002)

## Step 1: Set Up automatictrader-api (Server)

```bash
ssh mirko@192.168.178.55
cd /opt/trading/automatictrader-api

# Install dependencies
bash scripts/bootstrap.sh

# Configure environment
cp .env.example .env
```

Edit `.env`:
```env
AT_WORKER_MODE=plan-only     # Start with plan-only (no IB sending yet)
AT_AUTO_PROMOTE=0             # Manual promotion for testing
```

## Step 2: Start automatictrader-api Services

**Terminal 1 - API Server**:
```bash
cd /home/mirko/data/workspace/automatictrader-api
bash scripts/run_dev.sh
# Should start on http://localhost:8080
```

**Terminal 2 - Worker Process**:
```bash
cd /home/mirko/data/workspace/automatictrader-api
bash scripts/worker_dev.sh
# Polls for pending intents and creates plans
```

## Step 3: Test the Connection

From traderunner directory:

```bash
cd /home/mirko/data/workspace/droid/traderunner

# Health check only
PYTHONPATH=src python -m trade.paper_trading_adapter \
  --signals artifacts/signals/current_signals_rudometkin.csv \
  --health-check-only

# Expected: ✓ API health check passed
```

## Step 4: Generate Test Signals

```bash
# Generate Rudometkin signals (backtest mode)
PYTHONPATH=src python -m signals.cli_rudometkin_moc \
  --symbols AAPL,MSFT \
  --start 2025-11-20 \
  --end 2025-11-22 \
  --output artifacts/signals/test_signals.csv

# Check the output
cat artifacts/signals/test_signals.csv
```

## Step 5: Send Signals to automatictrader-api

```bash
# Send signals as order intents
PYTHONPATH=src python -m trade.paper_trading_adapter \
  --signals artifacts/signals/test_signals.csv \
  --api-url http://localhost:8080

# Expected output:
# ✓ API health check passed
# Intent created: id=1 symbol=AAPL side=LONG qty=10
# ...
# SUMMARY:
#   Total signals:     2
#   Created intents:   2
#   Duplicates:        0
#   Skipped:           0
#   Errors:            0
```

## Step 6: Verify Intent Processing

Check the automatictrader-api database:

```bash
cd /opt/trading/automatictrader-api

# View all intents
python3 -c "import sqlite3; c=sqlite3.connect('data/automatictrader.db'); [print(r) for r in c.execute('SELECT id,symbol,side,quantity,status FROM order_intents ORDER BY id DESC LIMIT 5')]"

# Expected:
# 1|AAPL|BUY|10|planned
# 2|MSFT|BUY|5|planned
```

Or use the API:

```bash
curl http://localhost:8080/intents?limit=5 | python -m json.tool
```

## Step 7: Test Idempotency

Send the same signals again:

```bash
PYTHONPATH=src python -m trade.paper_trading_adapter \
  --signals artifacts/signals/test_signals.csv \
  --api-url http://localhost:8080

# Expected:
#   Total signals:     2
#   Created intents:   0
#   Duplicates:        2    ← Idempotency working!
```

## Step 8: Enable IB Sending (Optional)

> [!CAUTION]
> Only proceed if you have IB Paper Trading account set up and TWS/Gateway running on port 4002

Edit `/home/mirko/data/workspace/automatictrader-api/.env`:

```env
AT_WORKER_MODE=paper-send          # Enable sending
AT_SEND_BACKEND=ib                 # Use IB directly
AT_AUTO_PROMOTE=1                  # Auto-promote to ready_to_send
AT_MARKET_GUARD=1                  # Only during market hours

AT_IB_HOST=127.0.0.1
AT_IB_PORT=4002                    # Paper trading port
AT_IB_CLIENT_ID=17

ENV_ALLOW_SEND=1                   # REQUIRED to actually send
ENV_FORCE_NO_IB=0                  # Set to 1 for dry-run
```

Restart the worker:
```bash
# Stop worker (Ctrl+C in Terminal 2)
# Start again
bash scripts/worker_dev.sh
```

## Step 9: Monitor Execution

**Check worker logs**:
```bash
# Terminal 2 shows:
# processing intent id=1 symbol=AAPL side=BUY qty=10 ot=MKT
# sending intent id=1 symbol=AAPL qty=10 via IB
# IB send ok: status=PreSubmitted orderId=123
# intent id=1 -> sent
```

**Check IB TWS**:
- Open IB Trader Workstation (Paper Account)
- View → Trade Log
- Should see orders submitted and filled

## Troubleshooting

### API Not Reachable
```bash
# Check if API is running
curl http://localhost:8080/healthz

# If not, check logs:
cd /home/mirko/data/workspace/automatictrader-api
cat logs/api.log  # or check Terminal 1 output
```

### Worker Not Processing
```bash
# Check worker is running (Terminal 2 should show polling logs)
# Check database:
sqlite3 data/automatictrader.db "SELECT COUNT(*), status FROM order_intents GROUP BY status;"

# Manually promote an intent:
curl -X POST http://localhost:8080/intents/1/promote
```

### IB Connection Failed
```bash
# Verify IB Gateway is running
# Check port is correct (4002 for paper, 4001 for live)
# Ensure ENV_ALLOW_SEND=1 is set
```

### Missing Signals File
```bash
# Generate new signals:
PYTHONPATH=src python -m signals.cli_rudometkin_moc \
  --symbols AAPL \
  --start 2025-11-20 \
  --end 2025-11-20
```

## Next Steps

Once basic integration is working:

1. **Add v2 Risk Guards** - Modify worker.py to include traderunner risk checks
2. **Real-Time Signals** - Add `--live-mode` to signal generation
3. **Scheduler** - Set up periodic signal generation with APScheduler
4. **Monitoring Dashboard** - Build Streamlit dashboard to view intents and fills

See `implementation_plan.md` for complete roadmap.
