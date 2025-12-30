#!/bin/bash
# Stop Pre-PaperTrade Session
# Stops all pre-papertrading services

echo "🛑 Stopping Pre-PaperTrade Services"
echo "===================================="
echo ""

# Kill processes by pattern matching
pkill -f "automatictrader.*app.py" && echo "✓ automatictrader-api stopped" || echo "  (not running)"
pkill -f "automatictrader.*worker.py" && echo "✓ automatictrader-worker stopped" || echo "  (not running)"
pkill -f "sqlite_bridge.py" && echo "✓ sqlite_bridge stopped" || echo "  (not running)"

echo ""
echo "✅ All services stopped"
echo ""
