---
description: Complete dashboard development and deployment workflow
---

# Trading Dashboard - Complete Workflow

This workflow guides you through the entire dashboard lifecycle from development to production.

## Phase 1: Development & Testing

### Step 1: Start Dashboard Locally
```bash
cd ~/data/workspace/droid/traderunner
source .venv/bin/activate
PYTHONPATH=. python trading_dashboard/app.py
```
**Expected:** Dashboard runs on http://localhost:9001 (admin/admin)

### Step 2: Verify Core Features
- [ ] Live Monitor tab shows watchlist, patterns, orders
- [ ] Portfolio tab shows $10,000 starting value
- [ ] Charts tab loads with MSFT symbol
- [ ] Chart stable on refresh (no random changes)
- [ ] Timeframe buttons work (M1, M5, M15, H1)
- [ ] Timezone switcher works (NY ↔ Berlin)

### Step 3: Test Real Data Integration
Check if real data sources are available:
```bash
# Check signals database
sqlite3 ~/data/workspace/droid/marketdata-stream/data/signals.db ".schema signals"

# Check trading database
sqlite3 ~/data/workspace/automatictrader-api/data/trading.db ".schema order_intents"
```

---

## Phase 2: Deploy to Test Environment

### Step 1: Copy to Server
```bash
rsync -avz --exclude='.venv' --exclude='__pycache__' \
  ~/data/workspace/droid/traderunner/trading_dashboard/ \
  mirko@192.168.178.55:/opt/trading/traderunner/trading_dashboard/
```

### Step 2: Install Dependencies on Server
```bash
ssh mirko@192.168.178.55
cd /opt/trading/traderunner
source .venv/bin/activate
pip install -r trading_dashboard/requirements.txt
```

### Step 3: Install Systemd Service
```bash
sudo cp trading_dashboard/systemd/trading-dashboard-v2.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable trading-dashboard-v2
sudo systemctl start trading-dashboard-v2
```

### Step 4: Verify Deployment
```bash
# Check service status
sudo systemctl status trading-dashboard-v2

# Check logs
sudo journalctl -u trading-dashboard-v2 -f

# Test access
curl -u admin:admin http://192.168.178.55:9001
```

**Expected:** Dashboard accessible at http://192.168.178.55:9001

---

## Phase 3: Production Hardening

### Step 1: Security
- [ ] Change admin password in environment variables
- [ ] Add HTTPS with nginx reverse proxy
- [ ] Restrict access to internal network only

### Step 2: Real Data Integration
- [ ] Connect to actual M5 candle database
- [ ] Implement position tracking table
- [ ] Add real-time price updates from marketdata-stream

### Step 3: Monitoring
- [ ] Set up alerts for dashboard downtime
- [ ] Add error tracking (e.g., Sentry)
- [ ] Create backup/restore procedures

---

## Phase 4: Feature Enhancements

### Priority 1: History Tab
- [ ] Implement date picker
- [ ] Create event timeline table
- [ ] Add CSV export functionality

### Priority 2: Real-Time Updates
- [ ] WebSocket connection to marketdata-stream
- [ ] Live price updates on watchlist
- [ ] Real-time order status changes

### Priority 3: Advanced Features
- [ ] Multi-strategy support (InsideBar + Rudometkin)
- [ ] Trade performance analytics
- [ ] Risk management dashboard

---

## Troubleshooting

### Dashboard won't start
```bash
# Check Python version
python --version  # Should be 3.12+

# Check dependencies
pip list | grep dash

# Check port availability
netstat -tuln | grep 9001
```

### Database errors
```bash
# Verify database paths in config
cat trading_dashboard/config.py | grep DB

# Check database exists
ls -lh ~/data/workspace/droid/marketdata-stream/data/signals.db
```

### Chart issues
- If chart changes on refresh: Check seed is deterministic (line 66 in candles.py)
- If timeframes don't work: Check callback inputs include tf-m1, tf-m5, etc.
- If timezone wrong: Verify pytz installed: `pip show pytz`

---

## Quick Commands

**Local dev:**
```bash
cd ~/data/workspace/droid/traderunner && source .venv/bin/activate && PYTHONPATH=. python trading_dashboard/app.py
```

**Deploy:**
```bash
/deploy-to-debian  # Use the deployment workflow
```

**Restart production:**
```bash
ssh mirko@192.168.178.55 "sudo systemctl restart trading-dashboard-v2"
```
