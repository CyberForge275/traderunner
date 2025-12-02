# Deployment Guide - Enhanced Trading Infrastructure

Created: 2025-12-02  
Purpose: Deploy today's infrastructure enhancements for paper trading

---

## 🚀 Quick Deployment Steps

### 1. Update Server IP in Deployment Script

```bash
# Edit the deployment script
nano /home/mirko/data/workspace/droid/traderunner/scripts/deploy_enhanced.sh

# Update this line (around line 8):
SERVER_HOST="YOUR_SERVER_IP"  # Change to your actual server IP
```

### 2. Run Deployment

```bash
cd /home/mirko/data/workspace/droid/traderunner
./scripts/deploy_enhanced.sh
```

**The script will**:
1. ✅ Backup current deployment
2. ✅ Sync all enhanced code
3. ✅ Install new dependencies (psutil)
4. ✅ Restart all services
5. ✅ Verify deployment with health checks

### 3. Verify Deployment

After the script completes, check the output for:
- ✅ All services show "active (running)"
- ✅ Health endpoints return "healthy"
- ✅ No errors in service logs

---

## 📋 Tomorrow's Paper Trading Session

Follow the detailed checklist: `docs/PAPER_TRADING_CHECKLIST.md`

### Pre-Market (9:00 ET / 15:00 CET)

1. **Start IB/TWS on your laptop** (Paper account)
2. **Check all services** are running on server
3. **Verify health endpoints** show "healthy"
4. **Confirm IB connection** settings

### During Market (9:30-16:00 ET)

1. **Monitor logs** in 3 terminal windows
2. **Watch for signals** being generated
3. **Verify orders** appear in IB TWS
4. **Health checks** every 30 minutes

### Post-Market (After 16:00 ET)

1. **Review signals/intents** generated
2. **Check error logs**
3. **Document issues**
4. **Plan improvements**

---

## 🎯 What's Been Enhanced

Today's deployment includes:

**Phase A1: Idempotency**
- Thread-safe LRU cache (10K keys)
- Performance: 321K keys/sec

**Phase A2: Error Handling**
- EODHD WebSocket auto-reconnection
- Circuit breakers (all services)
- Database retry logic
- IB/TWS connection resilience

**Phase A3: Monitoring**
- Enhanced `/health` endpoints
- Resource metrics (CPU, memory)
- Circuit breaker status
- Correlation ID support

**Phase B2: Risk Management**
- Dynamic position sizing (2% risk default)
- Drawdown protection (10% threshold)
- Enhanced concentration limits

---

## 🚨 Troubleshooting

### If Deployment Fails

```bash
# Check the backup location (shown in script output)
ls -la /opt/trading_backup_*

# Restore from backup if needed
ssh mirko@SERVER "cp -r /opt/trading_backup_TIMESTAMP/* /opt/trading/"
```

### If Services Won't Start

```bash
# Check service logs
ssh mirko@SERVER "sudo journalctl -u marketdata-stream -n 50"
ssh mirko@SERVER "sudo journalctl -u automatictrader-api -n 50"

# Common issues:
# - Missing dependencies: cd to service dir, activate venv, pip install -r requirements.txt
# - Port conflicts: check if old process still running
# - File permissions: chown -R mirko:mirko /opt/trading
```

### If Health Checks Fail

```bash
# Direct service logs
ssh mirko@SERVER "tail -f /opt/trading/marketdata-stream/logs/*.log"

# Python errors
ssh mirko@SERVER "cd /opt/trading/marketdata-stream && source .venv/bin/activate && python -c 'import psutil; print(\"OK\")'"
```

---

## 📞 Support Files

- **Deployment Script**: `scripts/deploy_enhanced.sh`
- **Pre-Market Checklist**: `docs/PAPER_TRADING_CHECKLIST.md`
- **Strategy Lifecycle**: `docs/STRATEGY_LIFECYCLE.md`
- **Docker Explanation**: See artifacts

---

## ✅ Deployment Checklist

- [ ] Updated SERVER_HOST in deploy script
- [ ] Ran deployment script successfully
- [ ] All services show "active (running)"
- [ ] Health endpoints return "healthy"
- [ ] No critical errors in logs
- [ ] IB/TWS configured for tomorrow
- [ ] Reviewed paper trading checklist

**You're ready for tomorrow's market open!** 🚀

---

## Next Session Goals

After successful paper trading:

1. **Docker containerization** (Phase D1) - For long-term stability
2. **Continuous monitoring** improvements
3. **Strategy optimization** based on real data
4. **Scale to live trading** (after validation period)

Good luck! 📈
