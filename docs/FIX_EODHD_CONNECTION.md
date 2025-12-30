# Pre-PaperTrade Service Configuration Steps

## ✅ Service is Running!

**Status**: marketdata-stream is active on port 8090 (not 8000)

```bash
# Correct health check command:
curl http://localhost:8090/health
```

## 🔧 Configuration Needed

The EODHD WebSocket is not connected. Need to update `.env` file.

### Step 1: Check Current Configuration

```bash
ssh mirko@192.168.178.55
cd /opt/trading/marketdata-stream
cat .env
```

### Step 2: Update .env File

```bash
# Edit the .env file
nano .env

# Make sure these lines are present:
EODHD_API_KEY=demo  # Or your actual API key
EODHD_ENDPOINT=us
WATCH_SYMBOLS=HOOD,PLTR,APP,INTC,TSLA,NVDA,MU,AVGO,LRCX,WBD
```

### Step 3: Restart Service

```bash
sudo systemctl restart marketdata-stream
```

### Step 4: Verify Connection

```bash
# Wait a few seconds, then check health
sleep 5
curl http://localhost:8090/health | jq '.'

# Should now show:
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

### Step 5: Watch Logs

```bash
# Monitor for tick data
sudo journalctl -u marketdata-stream -f | grep -E 'tick|WebSocket|error'
```

## 📋 Expected Output

Once configured correctly:
- ✅ EODHD WebSocket connected
- ✅ 10 symbols subscribed
- ✅ Tick data flowing
- ✅ No errors

## ⚠️ Port Note

**Important**: The service runs on **port 8090**, not 8000!

Update any scripts/docs that reference port 8000 to use 8090.

---

Once EODHD is connected, you're ready for tomorrow's Pre-PaperTrade session!
