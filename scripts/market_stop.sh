#!/bin/bash
# Market Hours Stop Script
# Stops marketdata-stream service at market close (4:00 PM ET / 22:00 CET)

set -e

LOG_FILE="/var/log/marketdata-trading.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] ===========================================" >> $LOG_FILE
echo "[$TIMESTAMP] Market Hours Stop - Stopping Services" >> $LOG_FILE
echo "[$TIMESTAMP] ===========================================" >> $LOG_FILE

# Get final statistics before stopping
if systemctl is-active --quiet marketdata-stream; then
    UPTIME=$(curl -s http://localhost:8090/health 2>/dev/null | grep -o '"uptime_seconds":[0-9]*' | cut -d':' -f2)
    SYMBOLS=$(curl -s http://localhost:8090/health 2>/dev/null | grep -o '"subscribed_symbols":[0-9]*' | cut -d':' -f2)

    echo "[$TIMESTAMP] Session statistics:" >> $LOG_FILE
    echo "[$TIMESTAMP]   - Uptime: ${UPTIME:-0} seconds" >> $LOG_FILE
    echo "[$TIMESTAMP]   - Symbols monitored: ${SYMBOLS:-0}" >> $LOG_FILE
fi

# Stop marketdata-stream
sudo systemctl stop marketdata-stream
sleep 2

# Verify stopped
if ! systemctl is-active --quiet marketdata-stream; then
    echo "[$TIMESTAMP] ✅ marketdata-stream stopped successfully" >> $LOG_FILE
else
    echo "[$TIMESTAMP] ⚠️  WARNING: marketdata-stream still running" >> $LOG_FILE
    # Force stop if needed
    sudo systemctl kill marketdata-stream
    sleep 1
    echo "[$TIMESTAMP] Force stopped marketdata-stream" >> $LOG_FILE
fi

echo "[$TIMESTAMP] Market hours ended - Services stopped" >> $LOG_FILE
echo "[$TIMESTAMP] Next start: Tomorrow at 15:30 CET (9:30 AM ET)" >> $LOG_FILE
echo "" >> $LOG_FILE
