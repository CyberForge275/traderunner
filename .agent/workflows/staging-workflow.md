---
description: Proper staging workflow - Test locally first, then deploy to production
---

# Staging → Production Workflow

> **Golden Rule**: Always test on local laptop (staging) before deploying to Debian server (production)

---

## Environment Overview

| Environment | Location | URL | Purpose |
|-------------|----------|-----|---------|
| **Staging** | Local Laptop | http://localhost:9001 | Testing & approval |
| **Production** | Debian Server | http://192.168.178.55:9001 | Live trading |

---

## Proper Deployment Workflow

### Step 1: Develop & Commit Changes ✅

// turbo

```bash
cd /home/mirko/data/workspace/droid/traderunner

# Make your changes...

# Commit to Git
git add .
git commit -m "feat: Your feature description"
git push origin feature/v2-architecture
```

---

### Step 2: Deploy to STAGING (Local) ✅

// turbo

```bash
# Restart local dashboard
pkill -f "trading_dashboard.app"
cd /home/mirko/data/workspace/droid/traderunner
PYTHONPATH=/home/mirko/data/workspace/droid/traderunner:$PYTHONPATH source .venv/bin/activate
nohup python -m trading_dashboard.app > /tmp/trading-dashboard-local.log 2>&1 &
```

**Verify**: http://localhost:9001

---

### Step 3: Test & Approve on STAGING 🧪

**Test Checklist**:
- [ ] Charts tab loads correctly
- [ ] Data displays as expected
- [ ] No errors in browser console (F12)
- [ ] Market session filters work
- [ ] Date selection works
- [ ] No bugs or visual issues

**Check Logs**:
```bash
tail -f /tmp/trading-dashboard-local.log
```

---

### Step 4: Deploy to PRODUCTION (Debian) 🚀

// turbo

**Only after staging approval!**

```bash
cd /home/mirko/data/workspace/droid/traderunner
./deploy-git.sh
```

**Verify**: http://192.168.178.55:9001

---

## Quick Commands

### Restart Staging (Local):
```bash
pkill -f "trading_dashboard.app" && cd /home/mirko/data/workspace/droid/traderunner && PYTHONPATH=/home/mirko/data/workspace/droid/traderunner:$PYTHONPATH source .venv/bin/activate && nohup python -m trading_dashboard.app > /tmp/trading-dashboard-local.log 2>&1 & sleep 3 && curl http://localhost:9001
```

### Deploy to Production (Debian):
```bash
cd /home/mirko/data/workspace/droid/traderunner && ./deploy-git.sh
```

---

## Rollback

### Staging (Local):
```bash
cd /home/mirko/data/workspace/droid/traderunner
git checkout <previous-commit>
pkill -f "trading_dashboard.app"
# Restart dashboard (see Step 2)
```

### Production (Debian):
```bash
ssh mirko@192.168.178.55
cd /opt/trading/traderunner
git checkout <previous-commit>
sudo systemctl restart trading-dashboard-v2
```

---

## Current Status

**Staging (Local)**: ✅ Running on http://localhost:9001
**Production (Debian)**: ✅ Running on http://192.168.178.55:9001
**Latest Commit**: `7fada89` (Bug fix: Future date validation)

Both environments are now synchronized!

---

## Best Practices

1. ✅ **Always test locally first** - Catch bugs before production
2. ✅ **Use git commits** - Know exactly what's deployed
3. ✅ **Test thoroughly on staging** - Don't rush to production
4. ✅ **Document changes** - Update CHANGELOG or release notes
5. ✅ **Monitor after deploy** - Check logs and dashboards

---

## Troubleshooting

### Staging won't start:
```bash
# Check if port 9001 is in use
netstat -tulpn | grep 9001

# Check logs
tail -f /tmp/trading-dashboard-local.log

# Try different port
python -m trading_dashboard.app --port 9002
```

### Production deploy fails:
```bash
# Check SSH connection
ssh mirko@192.168.178.55

# Check service status
ssh mirko@192.168.178.55 "sudo systemctl status trading-dashboard-v2"

# View deployment logs
ssh mirko@192.168.178.55 "sudo journalctl -u trading-dashboard-v2 -n 50"
```

---

## Summary

✅ **Local Laptop** = Your development and testing environment
✅ **Debian Server** = Production environment for live trading
✅ **Always**: Local → Test → Approve → Production
