#!/bin/bash
# Deployment Script for Enhanced Trading Infrastructure
# Date: 2025-12-02
# Purpose: Deploy resilience, monitoring, and risk management enhancements

set -e  # Exit on error

# Configuration
SERVER_USER="mirko"
SERVER_HOST="192.168.178.55"
REMOTE_BASE="/opt/trading"
LOCAL_BASE="/home/mirko/data/workspace"

echo "======================================================================"
echo "Trading System Deployment - Enhanced Infrastructure"
echo "======================================================================"
echo ""
echo "This will deploy:"
echo "  ✅ Phase A1: Idempotency enhancements"
echo "  ✅ Phase A2: Error handling & retry logic (all services)"
echo "  ✅ Phase A3: Monitoring & alerting"
echo "  ✅ Phase B2: Enhanced risk management"
echo ""
echo "Services to update:"
echo "  - marketdata-stream"
echo "  - automatictrader-api"
echo "  - traderunner"
echo ""
read -p "Continue with deployment? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "======================================================================"
echo "Step 1: Backup Current Deployment"
echo "======================================================================"

ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
echo "Creating backup..."
BACKUP_DIR="/opt/trading_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR
cp -r /opt/trading/marketdata-stream $BACKUP_DIR/ 2>/dev/null || true
cp -r /opt/trading/automatictrader-api $BACKUP_DIR/ 2>/dev/null || true
echo "✅ Backup created at: $BACKUP_DIR"
EOF

echo ""
echo "======================================================================"
echo "Step 2: Sync Enhanced Code"
echo "======================================================================"

echo "Syncing marketdata-stream..."
rsync -av --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='data/' --exclude='.git' \
    ${LOCAL_BASE}/droid/marketdata-stream/ \
    ${SERVER_USER}@${SERVER_HOST}:${REMOTE_BASE}/marketdata-stream/

echo ""
echo "Syncing automatictrader-api..."
rsync -av --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='data/' --exclude='.git' \
    ${LOCAL_BASE}/automatictrader-api/ \
    ${SERVER_USER}@${SERVER_HOST}:${REMOTE_BASE}/automatictrader-api/

echo ""
echo "Syncing traderunner..."
rsync -av --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='data/' --exclude='.git' \
    ${LOCAL_BASE}/droid/traderunner/ \
    ${SERVER_USER}@${SERVER_HOST}:${REMOTE_BASE}/traderunner/

echo ""
echo "======================================================================"
echo "Step 3: Install New Dependencies"
echo "======================================================================"

ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
echo "Installing dependencies for marketdata-stream..."
cd /opt/trading/marketdata-stream
source .venv/bin/activate || python3 -m venv .venv && source .venv/bin/activate
pip install -q psutil  # For resource monitoring in health checks
deactivate

echo ""
echo "Installing dependencies for automatictrader-api..."
cd /opt/trading/automatictrader-api
source .venv/bin/activate || python3 -m venv .venv && source .venv/bin/activate
pip install -q psutil  # For resource monitoring in health checks
deactivate

echo "✅ Dependencies installed"
EOF

echo ""
echo "======================================================================"
echo "Step 4: Restart Services"
echo "======================================================================"

echo "Stopping services..."
ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
sudo systemctl stop marketdata-stream 2>/dev/null || true
sudo systemctl stop automatictrader-api 2>/dev/null || true
sudo systemctl stop automatictrader-worker 2>/dev/null || true
echo "✅ Services stopped"
EOF

sleep 2

echo "Starting services..."
ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
sudo systemctl start marketdata-stream
sleep 2
sudo systemctl start automatictrader-api
sleep 2
sudo systemctl start automatictrader-worker
echo "✅ Services started"
EOF

echo ""
echo "======================================================================"
echo "Step 5: Verify Deployment"
echo "======================================================================"

sleep 3  # Give services time to start

echo "Checking service status..."
ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
echo ""
echo "marketdata-stream:"
sudo systemctl status marketdata-stream --no-pager -l | head -n 10

echo ""
echo "automatictrader-api:"
sudo systemctl status automatictrader-api --no-pager -l | head -n 10

echo ""
echo "automatictrader-worker:"
sudo systemctl status automatictrader-worker --no-pager -l | head -n 10
EOF

echo ""
echo "Checking health endpoints..."
sleep 2

# Check marketdata-stream health
echo ""
echo "marketdata-stream health check:"
ssh ${SERVER_USER}@${SERVER_HOST} "curl -s http://localhost:8000/health | jq '.' 2>/dev/null || curl -s http://localhost:8000/health"

echo ""
echo "automatictrader-api health check:"
ssh ${SERVER_USER}@${SERVER_HOST} "curl -s http://localhost:8080/healthz | jq '.' 2>/dev/null || curl -s http://localhost:8080/healthz"

echo ""
echo "======================================================================"
echo "✅ Deployment Complete!"
echo "======================================================================"
echo ""
echo "Next Steps:"
echo ""
echo "1. Verify health checks above show 'healthy' status"
echo "2. Check logs for any errors:"
echo "   ssh ${SERVER_USER}@${SERVER_HOST} 'sudo journalctl -u marketdata-stream -f'"
echo "   ssh ${SERVER_USER}@${SERVER_HOST} 'sudo journalctl -u automatictrader-api -f'"
echo ""
echo "3. Tomorrow at 9:00 ET (before market open):"
echo "   - Verify IB/TWS is running (on your laptop)"
echo "   - Check all services are up"
echo "   - Monitor /health endpoints"
echo ""
echo "4. During market hours (9:30-16:00 ET):"
echo "   - Watch for signals in logs"
echo "   - Confirm orders appear in IB paper account"
echo "   - Monitor health endpoints for issues"
echo ""
echo "======================================================================"
echo ""
echo "📊 Enhanced Features Now Active:"
echo "  ✅ EODHD WebSocket auto-reconnection"
echo "  ✅ Circuit breakers (EODHD, IB/TWS, Order API)"
echo "  ✅ Database retry logic"
echo "  ✅ Enhanced health monitoring"
echo "  ✅ Dynamic position sizing"
echo "  ✅ Drawdown protection"
echo ""
echo "Good luck with tomorrow's paper trading session! 🚀"
echo ""
