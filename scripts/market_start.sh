#!/bin/bash
# Market Hours Start Script
# Starts marketdata-stream service at market open (9:30 AM ET / 15:30 CET)

set -e

LOG_FILE="/var/log/marketdata-trading.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] ===========================================" >> $LOG_FILE
echo "[$TIMESTAMP] Market Hours Start - Starting Services" >> $LOG_FILE
echo "[$TIMESTAMP] ===========================================" >> $LOG_FILE

# Start marketdata-stream
sudo systemctl start marketdata-stream
sleep 3

# Check if service started successfully
if systemctl is-active --quiet marketdata-stream; then
    echo "[$TIMESTAMP] ✅ marketdata-stream started successfully" >> $LOG_FILE

    # Wait a moment for WebSocket connection
    sleep 5

    # Check health endpoint
    HEALTH_STATUS=$(curl -s http://localhost:8090/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    echo "[$TIMESTAMP] Health status: $HEALTH_STATUS" >> $LOG_FILE

    # Check EODHD connection
    EODHD_CONNECTED=$(curl -s http://localhost:8090/health | grep -o '"connected":[^,]*' | cut -d':' -f2)
    echo "[$TIMESTAMP] EODHD connected: $EODHD_CONNECTED" >> $LOG_FILE
else
    echo "[$TIMESTAMP] ❌ ERROR: marketdata-stream failed to start" >> $LOG_FILE
    exit 1
fi

echo "[$TIMESTAMP] Market hours automation activated" >> $LOG_FILE
echo "[$TIMESTAMP] Services will run until 22:00 CET (market close)" >> $LOG_FILE
