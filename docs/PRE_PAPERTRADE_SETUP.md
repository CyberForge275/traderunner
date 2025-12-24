# Pre-PaperTrade Lab Configuration

> **Last Updated**: 2025-12-05  
> **Server**: 192.168.178.55 (Debian)  
> **Port**: 8090

**Mode**: Stage 3 - Live Data Validation (Read-Only)  
**Goal**: Validate signal generation with live ticks, NO order submission

---

## Configuration Overview

### Mode: Pre-PaperTrade Lab

In this mode:
- ✅ **marketdata-stream** connects to EODHD (live ticks)
- ✅ **Strategy module** generates signals
- ✅ **Signals stored** in `signals.db` for review
- ❌ **signal_processor DISABLED** (no API submission)
- ❌ **automatictrader-api** not involved
- ❌ **No orders sent** to IB

---

## Stock Symbols Configuration

**REQUIRED**: Update with your symbols before deployment!

### Current Symbols (Production)

```bash
# In marketdata-stream .env (server: /opt/trading/marketdata-stream/.env)
EODHD_SYMBOLS=HOOD,PLTR,APP,INTC,TSLA,NVDA,MU,AVGO,LRCX,WBD
```

### Option 2: Custom List

**Please provide your symbol list here:**
- Symbol 1: __________
- Symbol 2: __________
- Symbol 3: __________
- Symbol 4: __________
- Symbol 5: __________

---

## Strategy Configuration

### Which Strategy to Run?

**Option A: Rudometkin MOC** (existing)
- File: `traderunner/src/signals/cli_rudometkin_moc.py`
- Generates: LONG/SHORT signals at market close
- Tested: ✅ Yes

**Option B: Inside Bar** (existing)
- File: `traderunner/src/signals/cli_inside_bar.py`
- Generates: Breakout signals
- Tested: ✅ Yes

**Option C: New Strategy**
- Needs: Implementation first
- Status: Not ready for Pre-PaperTrade

**Selected Strategy**: __________ (Update this!)

---

## Deployment Steps for Pre-PaperTrade

### Step 1: Configure Environment

```bash
# SSH to server
ssh mirko@YOUR_SERVER_IP

# Edit marketdata-stream configuration
cd /opt/trading/marketdata-stream
nano .env

# Add/Update these lines:
EODHD_API_KEY=your_key_here
EODHD_ENDPOINT=us
EODHD_SYMBOLS=HOOD,PLTR,APP,INTC,TSLA,NVDA,MU,AVGO,LRCX,WBD

# CRITICAL: Ensure signal_processor is NOT started
# (We'll verify this in systemd)
```

### Step 2: Disable signal_processor Service

```bash
# Make sure signal_processor is NOT running (Pre-PaperTrade mode)
sudo systemctl stop signal_processor 2>/dev/null || true
sudo systemctl disable signal_processor 2>/dev/null || true

# Verify it's stopped
sudo systemctl status signal_processor
# Should show: inactive (dead) or not found
```

### Step 3: Run Deployment Script

```bash
cd /home/mirko/data/workspace/droid/traderunner
./scripts/deploy_enhanced.sh
```

### Step 4: Start Only marketdata-stream

```bash
# On server
sudo systemctl start marketdata-stream

# Verify it's running
sudo systemctl status marketdata-stream

# Should show: active (running)
```

### Step 5: Verify Configuration

```bash
# Check EODHD connection
curl http://localhost:8090/health | python3 -m json.tool

# Should show:
# {
#   "connected": true,
#   "subscribed_symbols": 5  # Or your count
# }

# Check signals database exists
ls -la /opt/trading/marketdata-stream/data/signals.db
```

---

## Strategy Integration

### How to Run Strategy

**Option 1: Embedded in marketdata-stream** (Recommended)
- Strategy runs as part of the stream service
- Generates signals automatically
- Requires: Strategy module integrated into app.py

**Option 2: Separate CLI Process** (Current)
- Run strategy CLI manually or via cron
- Writes to signals.db
- More flexible for testing

### For Tomorrow's Session - Use Option 2 (Manual)

```bash
# On server during market hours
ssh mirko@YOUR_SERVER_IP

# Navigate to traderunner
cd /opt/trading/traderunner
source .venv/bin/activate

# Run strategy (example with Rudometkin)
python -m src.signals.cli_rudometkin_moc \
    --symbols AAPL,TSLA,NVDA \
    --output /opt/trading/marketdata-stream/data/signals.db

# This will:
# 1. Fetch latest data
# 2. Generate signals
# 3. Store in signals.db
```

---

## Monitoring During Pre-PaperTrade

### Terminal 1: Watch marketdata-stream logs

```bash
ssh mirko@YOUR_SERVER_IP
sudo journalctl -u marketdata-stream -f | grep -E 'tick|signal|error'
```

**Look for:**
- ✅ WebSocket connected
- ✅ Ticks flowing for your symbols
- ✅ No errors

### Terminal 2: Watch signals database

```bash
ssh mirko@YOUR_SERVER_IP

# Watch for new signals (run periodically)
watch -n 5 "sqlite3 /opt/trading/marketdata-stream/data/signals.db \
  'SELECT id, symbol, side, entry_price, created_at FROM signals ORDER BY created_at DESC LIMIT 5;'"
```

**Look for:**
- ✅ New signals appearing
- ✅ Correct symbols
- ✅ Prices look reasonable

### Terminal 3: Strategy output (if running manually)

```bash
# When you run the strategy CLI
cd /opt/trading/traderunner
source .venv/bin/activate
python -m src.signals.cli_rudometkin_moc --symbols AAPL,TSLA --output /opt/trading/marketdata-stream/data/signals.db
```

**Look for:**
- ✅ Strategy completed successfully
- ✅ X signals generated
- ✅ Written to database

---

## Review Signals After Market Close

```bash
# Connect to database
sqlite3 /opt/trading/marketdata-stream/data/signals.db

# Get summary of today's signals
SELECT 
    symbol,
    side,
    COUNT(*) as signal_count,
    AVG(entry_price) as avg_entry_price
FROM signals 
WHERE DATE(created_at) = DATE('now')
GROUP BY symbol, side;

# Get detailed signal list
SELECT 
    id,
    symbol,
    side,
    quantity,
    entry_price,
    stop_loss,
    take_profit,
    created_at,
    status
FROM signals 
WHERE DATE(created_at) = DATE('now')
ORDER BY created_at DESC;

# Export to CSV for analysis
.mode csv
.headers on
.output /tmp/signals_2025_12_03.csv
SELECT * FROM signals WHERE DATE(created_at) = DATE('now');
.quit
```

---

## Success Criteria for Pre-PaperTrade

✅ **Technical Success:**
- [ ] marketdata-stream receives live ticks
- [ ] Strategy generates signals
- [ ] Signals stored correctly in database
- [ ] No critical errors
- [ ] Latency acceptable (< 1 second tick → signal)

✅ **Signal Quality:**
- [ ] Signals match backtest expectations
- [ ] Entry prices look reasonable
- [ ] Stop loss / take profit calculated correctly
- [ ] No unexpected symbols
- [ ] No duplicate signals

✅ **Validation:**
- [ ] Review each signal manually
- [ ] Cross-check with charts if questionable
- [ ] Document any false positives
- [ ] Note timing of signals

---

## Next Steps After Pre-PaperTrade Success

1. **If signals look good** → Proceed to Stage 4 (PaperTrade)
   - Enable signal_processor
   - Start automatictrader-api + worker
   - Orders will flow to IB paper account

2. **If signals need adjustment** → Stay in Pre-PaperTrade
   - Tune strategy parameters
   - Test with different symbols
   - Re-run until satisfied

3. **If major issues** → Back to Backtesting Lab
   - Debug strategy logic
   - Fix any bugs discovered
   - Re-validate with historical data

---

## Quick Reference

| Component | Status | Purpose |
|-----------|--------|---------|
| **marketdata-stream** | ✅ Running | Receive live ticks, run strategy |
| **signal_processor** | ❌ Disabled | NO submission to API |
| **automatictrader-api** | ❌ Stopped | Not needed in Stage 3 |
| **automatictrader-worker** | ❌ Stopped | Not needed in Stage 3 |
| **traderunner** | ⚙️ Manual | Run strategy CLI as needed |

---

## Configuration Checklist

- [ ] Stock symbols defined
- [ ] Strategy selected
- [ ] EODHD API key configured
- [ ] signal_processor disabled
- [ ] marketdata-stream configured
- [ ] Deployment script updated with server IP
- [ ] Ready to deploy

**Fill in the required information above, then deploy!**
