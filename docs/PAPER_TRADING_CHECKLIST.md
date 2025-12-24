# Pre-Market Checklist for Paper Trading

**Date**: _________  
**Market Open**: 9:30 ET / 15:30 CET  
**Market Close**: 16:00 ET / 22:00 CET

---

## 🕐 9:00 AM ET (15:00 CET) - Pre-Market Setup

### On Your Laptop (IB/TWS)
- [ ] Start Interactive Brokers TWS
- [ ] Log in to **Paper Trading Account**
- [ ] Verify connection status (green light)
- [ ] Check account balance
- [ ] Enable API connections (Configure → Settings → API → Enable ActiveX and Socket Clients)
- [ ] Note TWS port (default: 4002 for paper, 7497 for live)

### On Server (Trading Services)

```bash
# SSH into server
ssh mirko@YOUR_SERVER_IP

# Check all services are running
sudo systemctl status marketdata-stream
sudo systemctl status automatictrader-api
sudo systemctl status automatictrader-worker

# If any service is down, restart:
sudo systemctl restart marketdata-stream
sudo systemctl restart automatictrader-api
sudo systemctl restart automatictrader-worker
```

### Health Check Verification

```bash
# Check marketdata-stream health
curl http://localhost:8000/health | jq '.'

# Expected:
# {
#   "status": "healthy",
#   "dependencies": {
#     "eodhd": {
#       "connected": true,
#       "circuit_breaker_state": "closed"
#     }
#   }
# }

# Check automatictrader-api health
curl http://localhost:8080/healthz | jq '.'

# Expected:
# {
#   "status": "healthy",
#   "dependencies": {
#     "database": "healthy",
#     "worker": "healthy"
#   }
# }
```

- [ ] marketdata-stream shows "healthy"
- [ ] EODHD connected: true
- [ ] automatictrader-api shows "healthy"
- [ ] Database: "healthy"
- [ ] Worker: "healthy"

### Configuration Verification

```bash
# Verify worker is in paper-send mode
ssh mirko@YOUR_SERVER_IP "grep AT_WORKER_MODE /opt/trading/automatictrader-api/.env"

# Should show: AT_WORKER_MODE=paper-send

# Verify IB connection settings point to your laptop
ssh mirko@YOUR_SERVER_IP "grep AT_IB_ /opt/trading/automatictrader-api/.env"

# Should show your laptop IP and port 4002
```

- [ ] Worker mode: paper-send
- [ ] IB host points to your laptop IP
- [ ] IB port: 4002 (paper trading)

---

## 🔔 9:30 AM ET - Market Open

### Start Monitoring

```bash
# Terminal 1: Watch marketdata-stream logs
ssh mirko@YOUR_SERVER_IP
sudo journalctl -u marketdata-stream -f

# Terminal 2: Watch automatictrader-api logs
ssh mirko@YOUR_SERVER_IP
sudo journalctl -u automatictrader-api -f

# Terminal 3: Watch worker logs
ssh mirko@YOUR_SERVER_IP
sudo journalctl -u automatictrader-worker -f
```

### What to Look For

**marketdata-stream logs:**
- ✅ "✅ WebSocket connection opened"
- ✅ Tick data flowing (symbol updates)
- ✅ No circuit breaker openings
- ⚠️ Watch for reconnection attempts

**automatictrader-api logs:**
- ✅ Intent creation requests
- ✅ Successful intent storage
- ⚠️ HTTP error codes

**worker logs:**
- ✅ "processing intent id=X"
- ✅ "intent id=X → planned"
- ✅ "intent id=X → ready"
- ✅ "IB send ok: status=PreSubmitted orderId=X"
- ⚠️ Connection errors to IB

### First Hour Checklist (9:30-10:30 ET)

- [ ] Ticks are flowing in marketdata-stream
- [ ] At least 1 signal generated (check logs or signals.db)
- [ ] Signal converted to order intent
- [ ] Intent processed by worker
- [ ] Order appears in IB paper account TWS
- [ ] No critical errors in any service

---

## 📊 During Market Hours (9:30-16:00 ET)

### Periodic Checks (Every 30 minutes)

```bash
# Quick health check
curl http://localhost:8000/health | jq '.status'
curl http://localhost:8080/healthz | jq '.status'

# Check for errors
sudo journalctl -u marketdata-stream --since "10 minutes ago" | grep -i error
sudo journalctl -u automatictrader-api --since "10 minutes ago" | grep -i error
sudo journalctl -u automatictrader-worker --since "10 minutes ago" | grep -i error
```

- [ ] 10:00 check: All healthy
- [ ] 10:30 check: All healthy
- [ ] 11:00 check: All healthy
- [ ] 11:30 check: All healthy
- [ ] 12:00 check: All healthy
- [ ] 12:30 check: All healthy
- [ ] 13:00 check: All healthy
- [ ] 13:30 check: All healthy
- [ ] 14:00 check: All healthy
- [ ] 14:30 check: All healthy
- [ ] 15:00 check: All healthy
- [ ] 15:30 check: All healthy

### Monitor IB Paper Account

In TWS:
- [ ] Check "Orders" tab for submitted orders
- [ ] Verify order details (symbol, side, quantity, price)
- [ ] Check "Executions" tab for fills
- [ ] Monitor account P&L

---

## 🏁 16:00 ET - Market Close

### Post-Market Analysis

```bash
# Check total signals generated
ssh mirko@YOUR_SERVER_IP
cd /opt/trading/marketdata-stream
sqlite3 data/signals.db "SELECT COUNT(*) FROM signals WHERE DATE(created_at) = DATE('now');"

# Check total intents created
cd /opt/trading/automatictrader-api
sqlite3 data/automatictrader.db "SELECT COUNT(*) FROM order_intents WHERE DATE(created_at) = DATE('now');"

# Check intent status distribution
sqlite3 data/automatictrader.db "SELECT status, COUNT(*) FROM order_intents WHERE DATE(created_at) = DATE('now') GROUP BY status;"
```

### Summary Report

**Signals Generated**: _____  
**Intents Created**: _____  
**Orders Sent to IB**: _____  
**Orders Filled**: _____  
**Critical Errors**: _____  
**Circuit Breaker Opens**: _____  

### Issues Encountered

1. _______________________________________________
2. _______________________________________________
3. _______________________________________________

### Action Items for Tomorrow

1. _______________________________________________
2. _______________________________________________
3. _______________________________________________

---

## 🚨 Emergency Procedures

### If Service Crashes

```bash
# Restart specific service
sudo systemctl restart marketdata-stream
sudo systemctl restart automatictrader-api
sudo systemctl restart automatictrader-worker

# Check why it crashed
sudo journalctl -u <service-name> --since "1 hour ago"
```

### If IB Connection Lost

1. Check TWS is running on your laptop
2. Verify API is enabled in TWS
3. Check firewall on laptop isn't blocking connections
4. Restart automatictrader-worker:
   ```bash
   sudo systemctl restart automatictrader-worker
   ```

### If Circuit Breaker Opens

```bash
# Check circuit breaker stats in health endpoint
curl http://localhost:8000/health | jq '.dependencies.eodhd.circuit_breaker_state'

# Wait for automatic recovery (2 minutes for EODHD, 1 minute for IB)
# Or manually restart service to reset
```

### Emergency Stop (Kill Switch)

```bash
# Stop all trading immediately
sudo systemctl stop automatictrader-worker

# Orders already in IB will still be live - cancel manually in TWS if needed
```

---

## 📝 Notes

Use this space for observations during the trading day:

_____________________________________________________________________

_____________________________________________________________________

_____________________________________________________________________

_____________________________________________________________________

---

**Remember**: This is paper trading - no real money at risk. Use this session to verify:
- ✅ Full signal → intent → order flow works
- ✅ Services are stable during market hours
- ✅ Error handling works as expected
- ✅ Monitoring provides adequate visibility

**Good luck!** 🚀
