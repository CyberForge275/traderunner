#!/bin/bash
# Start Pre-PaperTrade Session
# Starts all required services for testing without IB connection

set -e

echo "🚀 Starting Pre-PaperTrade Session"
echo "=================================="
echo ""

# Check if services are already running
if pgrep -f "automatictrader.*app.py" > /dev/null; then
    echo "⚠️  automatictrader-api already running"
else
    echo "1️⃣  Starting automatictrader-api..."
    cd /home/mirko/data/workspace/automatictrader-api
    source .venv/bin/activate
    nohup python app.py > /tmp/automatictrader-api.log 2>&1 &
    API_PID=$!
    echo "   ✓ API started (PID: $API_PID)"
    deactivate
    sleep 1
fi

if pgrep -f "automatictrader.*worker.py" > /dev/null; then
    echo "⚠️  automatictrader-worker already running"
else
    echo "2️⃣  Starting automatictrader-worker..."
    cd /home/mirko/data/workspace/automatictrader-api
    source .venv/bin/activate
    nohup python worker.py > /tmp/automatictrader-worker.log 2>&1 &
    WORKER_PID=$!
    echo "   ✓ Worker started (PID: $WORKER_PID)"
    deactivate
    sleep 1
fi

if pgrep -f "sqlite_bridge.py" > /dev/null; then
    echo "⚠️  sqlite_bridge already running"
else
    echo "3️⃣  Starting sqlite_bridge..."
    cd /home/mirko/data/workspace/droid/marketdata-stream
    source .venv/bin/activate
    nohup python sqlite_bridge.py > /tmp/sqlite_bridge.log 2>&1 &
    BRIDGE_PID=$!
    echo "   ✓ Bridge started (PID: $BRIDGE_PID)"
    deactivate
    sleep 1
fi

echo ""
echo "✅ All services started!"
echo ""
echo "Running processes:"
ps aux | grep -E "(app.py|worker.py|sqlite_bridge.py)" | grep -v grep | awk '{print "   " $2 " - " $11 " " $12}'
echo ""
echo "📊 Dashboard: http://localhost:9001"
echo "   Go to 'Pre-PaperTrade Lab' tab to run tests"
echo ""
echo "📝 Logs:"
echo "   tail -f /tmp/automatictrader-api.log"
echo "   tail -f /tmp/automatictrader-worker.log"
echo "   tail -f /tmp/sqlite_bridge.log"
echo ""
echo "To stop services:"
echo "   bash $(dirname "$0")/stop_pre_papertrade_session.sh"
echo ""
