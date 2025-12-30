# Market Hours Automation Setup Guide

## Overview

Automated start/stop of trading services during NYSE market hours:
- **Start**: 15:30 CET (9:30 AM ET) - Market open
- **Stop**: 22:00 CET (4:00 PM ET) - Market close
- **Days**: Monday-Friday only

---

## Installation Steps

### 1. Copy Scripts to Server

```bash
# From your laptop
cd /home/mirko/data/workspace/droid/traderunner
rsync -av scripts/market_start.sh scripts/market_stop.sh mirko@192.168.178.55:/tmp/

# SSH to server
ssh mirko@192.168.178.55

# Create scripts directory and move files
sudo mkdir -p /opt/trading/scripts
sudo mv /tmp/market_start.sh /opt/trading/scripts/
sudo mv /tmp/market_stop.sh /opt/trading/scripts/
sudo chown mirko:mirko /opt/trading/scripts/*.sh
sudo chmod +x /opt/trading/scripts/*.sh
```

### 2. Create Log File

```bash
# On server
sudo touch /var/log/marketdata-trading.log
sudo chown mirko:mirko /var/log/marketdata-trading.log
```

### 3. Test Scripts Manually

```bash
# Test start script
/opt/trading/scripts/market_start.sh

# Check if service started
systemctl status marketdata-stream

# Check logs
tail -f /var/log/marketdata-trading.log

# Test stop script
/opt/trading/scripts/market_stop.sh

# Verify stopped
systemctl status marketdata-stream
```

### 4. Install Cron Jobs

```bash
# Edit crontab
crontab -e

# Add these lines (copy from market_hours.cron):
30 15 * * 1-5 /opt/trading/scripts/market_start.sh
0 22 * * 1-5 /opt/trading/scripts/market_stop.sh
0 0 * * * [ -f /var/log/marketdata-trading.log ] && tail -n 1000 /var/log/marketdata-trading.log > /var/log/marketdata-trading.log.tmp && mv /var/log/marketdata-trading.log.tmp /var/log/marketdata-trading.log

# Save and exit
```

### 5. Verify Cron Installation

```bash
# List current cron jobs
crontab -l

# Should show the three entries above
```

---

## How It Works

### Daily Workflow

**15:30 CET (9:30 AM ET) - Market Open:**
1. `market_start.sh` executes
2. Starts `marketdata-stream` service
3. Waits 5 seconds for initialization
4. Checks health endpoint
5. Logs connection status

**22:00 CET (4:00 PM ET) - Market Close:**
1. `market_stop.sh` executes
2. Captures session statistics
3. Stops `marketdata-stream` service
4. Logs session summary

**00:00 CET (Midnight):**
1. Log rotation runs
2. Keeps last 1000 lines
3. Prevents log file from growing too large

---

## Monitoring

### Check Logs

```bash
# View today's activity
tail -50 /var/log/marketdata-trading.log

# Watch live
tail -f /var/log/marketdata-trading.log

# Search for errors
grep ERROR /var/log/marketdata-trading.log

# View specific date
grep "2025-12-03" /var/log/marketdata-trading.log
```

### Manual Override

```bash
# Start service manually (outside market hours)
sudo systemctl start marketdata-stream

# Stop service manually (during market hours)
sudo systemctl stop marketdata-stream

# Cron will resume automation next scheduled time
```

---

## Timezone Considerations

**Cron uses server timezone** (Europe/Berlin):
- ✅ CET (Winter): UTC+1
- ✅ CEST (Summer): UTC+2

**NYSE market hours** (America/New_York):
- Eastern Standard Time (Winter): UTC-5
- Eastern Daylight Time (Summer): UTC-4

**Time mapping:**

| Season | NYSE Market | CET/CEST | Cron Time |
|--------|-------------|----------|-----------|
| **Winter (Nov-Mar)** | 9:30 AM EST | 15:30 CET | 15:30 ✅ |
| **Winter (Nov-Mar)** | 4:00 PM EST | 22:00 CET | 22:00 ✅ |
| **Summer (Mar-Nov)** | 9:30 AM EDT | 15:30 CEST | 15:30 ✅ |
| **Summer (Mar-Nov)** | 4:00 PM EDT | 22:00 CEST | 22:00 ✅ |

**Lucky coincidence**: The time difference stays the same year-round because both zones observe daylight saving!

---

## Troubleshooting

### Scripts Don't Run

```bash
# Check cron is running
systemctl status cron

# Check cron logs
grep CRON /var/log/syslog | tail -20

# Verify script permissions
ls -la /opt/trading/scripts/
# Should show: -rwxr-xr-x (executable)
```

### Service Doesn't Start

```bash
# Check script output
tail -50 /var/log/marketdata-trading.log

# Manually run start script
/opt/trading/scripts/market_start.sh

# Check service status
systemctl status marketdata-stream

# Check service logs
journalctl -u marketdata-stream -n 50 --no-pager
```

### Wrong Time Zone

```bash
# Check server timezone
timedatectl

# Should show: Europe/Berlin

# If wrong, set correct timezone
sudo timedatectl set-timezone Europe/Berlin
```

---

## Testing Schedule

### Simulate Tomorrow's Run

```bash
# Force start (as if it's 15:30)
/opt/trading/scripts/market_start.sh

# Wait a few seconds
sleep 10

# Check it's running
curl http://localhost:8090/health | jq '.dependencies.eodhd.connected'

# Force stop (as if it's 22:00)
/opt/trading/scripts/market_stop.sh

# Verify it's stopped
systemctl is-active marketdata-stream
# Should show: inactive
```

---

## Log Examples

### Successful Start
```
[2025-12-03 15:30:01] ===========================================
[2025-12-03 15:30:01] Market Hours Start - Starting Services
[2025-12-03 15:30:01] ===========================================
[2025-12-03 15:30:04] ✅ marketdata-stream started successfully
[2025-12-03 15:30:09] Health status: healthy
[2025-12-03 15:30:09] EODHD connected: true
[2025-12-03 15:30:09] Market hours automation activated
[2025-12-03 15:30:09] Services will run until 22:00 CET (market close)
```

### Successful Stop
```
[2025-12-03 22:00:01] ===========================================
[2025-12-03 22:00:01] Market Hours Stop - Stopping Services
[2025-12-03 22:00:01] ===========================================
[2025-12-03 22:00:01] Session statistics:
[2025-12-03 22:00:01]   - Uptime: 23400 seconds
[2025-12-03 22:00:01]   - Symbols monitored: 10
[2025-12-03 22:00:03] ✅ marketdata-stream stopped successfully
[2025-12-03 22:00:03] Market hours ended - Services stopped
[2025-12-03 22:00:03] Next start: Tomorrow at 15:30 CET (9:30 AM ET)
```

---

## Benefits

✅ **Fully Automated**: No manual intervention needed
✅ **Market Hours Only**: Runs only when NYSE is open
✅ **Logged**: Full audit trail of all starts/stops
✅ **Robust**: Health checks and error handling
✅ **Weekend Aware**: Skips Saturdays and Sundays
✅ **Log Rotation**: Prevents disk space issues

---

## What's Next

Once this runs successfully for a few days:
1. Add automatictrader-api to start/stop scripts
2. Add signal_processor to automation
3. Add automatictrader-worker for paper trading
4. Scale to full automated paper trading system

**Your system will wake up every trading day and work automatically!** 🚀
