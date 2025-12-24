# Manual Deployment Steps - Pre-PaperTrade Lab

## ✅ Already Completed (Automated)

1. ✅ Backup created
2. ✅ Code synced to server (marketdata-stream + automatictrader-api)
3. ✅ Virtual environments created
4. ✅ All dependencies installed (fastapi, uvicorn, psutil, etc.)
5. ✅ Services stopped

## 🔧 Manual Steps Required

### Step 1: Start marketdata-stream Service

```bash
# SSH to server
ssh mirko@192.168.178.55

# Start the service
sudo systemctl start marketdata-stream

# Verify it's running
sudo systemctl status marketdata-stream

# Should show: active (running)
```

### Step 2: Verify Health

```bash
# Check health endpoint
curl http://localhost:8000/health | jq '.'

# Expected output:
# {
#   "status": "healthy",
#   "dependencies": {
#     "eodhd": {
#       "connected": true,
#       "subscribed_symbols": 10
#     }
#   }
# }
```

### Step 3: Verify Logs

```bash
# Watch logs for any errors
sudo journalctl -u marketdata-stream -f

# Look for:
# ✅ "WebSocket connection opened"
# ✅ Tick data for symbols (HOOD, PLTR, etc.)
# ✅ No errors
```

## 📋 Configuration Applied

**Symbols** (10 stocks):
- HOOD, PLTR, APP, INTC, TSLA
- NVDA, MU, AVGO, LRCX, WBD

**Strategy**: InsideBar (ready to run)

**Mode**: Pre-PaperTrade (read-only, no order submission)

## 🚀 Ready for Tomorrow

Once the service starts successfully:
- ✅ It will connect to EODHD
- ✅ Subscribe to your 10 symbols
- ✅ Receive live tick data
- ✅ Ready for InsideBar strategy testing

## ⏭️ Next Steps

Tomorrow during market hours (9:30-16:00 ET / 15:30-22:00 CET):

1. **Run InsideBar strategy manually**:
   ```bash
   cd /opt/trading/traderunner
   source .venv/bin/activate
   python -m src.signals.cli_inside_bar \
       --symbols HOOD,PLTR,APP,INTC,TSLA,NVDA,MU,AVGO,LRCX,WBD \
       --output /opt/trading/marketdata-stream/data/signals.db
   ```

2. **Monitor signal generation**:
   ```bash
   watch -n 5 "sqlite3 /opt/trading/marketdata-stream/data/signals.db \
     'SELECT * FROM signals ORDER BY created_at DESC LIMIT 5;'"
   ```

3. **Review signals after market close**

---

**Everything is deployed and configured! Just need to start the service.**
