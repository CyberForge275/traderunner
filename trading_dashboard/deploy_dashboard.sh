#!/bin/bash
#
# Deploy Trading Dashboard to Debian Server
# Usage: ./deploy_dashboard.sh
#

set -e  # Exit on error

# Configuration
SERVER="mirko@192.168.178.55"
REMOTE_DIR="/opt/trading/traderunner"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "===================================================="
echo "Trading Dashboard Deployment Script"
echo "===================================================="
echo "Server: $SERVER"
echo "Remote: $REMOTE_DIR"
echo "Local: $LOCAL_DIR"
echo "===================================================="

# Step 1: Run tests locally
echo ""
echo "[1/6] Running automated tests..."
cd ..
source .venv/bin/activate
cd trading_dashboard
PYTHONPATH=.. pytest tests/ -v
if [ $? -ne 0 ]; then
    echo "❌ Tests failed! Deployment aborted."
    exit 1
fi
echo "✅ All tests passed!"

# Step 2: Copy files to server
echo ""
echo "[2/6] Copying files to server..."
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
    ../trading_dashboard/ \
    $SERVER:$REMOTE_DIR/trading_dashboard/

if [ $? -ne 0 ]; then
    echo "❌ File copy failed! Deployment aborted."
    exit 1
fi
echo "✅ Files copied successfully!"

# Step 3: Install dependencies on server
echo ""
echo "[3/6] Installing dependencies on server..."
ssh $SERVER "cd $REMOTE_DIR && source .venv/bin/activate && pip install -r trading_dashboard/requirements.txt -q"
if [ $? -ne 0 ]; then
    echo "❌ Dependency installation failed!"
    exit 1
fi
echo "✅ Dependencies installed!"

# Step 4: Install systemd service
echo ""
echo "[4/6] Installing systemd service..."
ssh $SERVER "sudo cp $REMOTE_DIR/trading_dashboard/systemd/trading-dashboard-v2.service /etc/systemd/system/ && \
    sudo systemctl daemon-reload && \
    sudo systemctl enable trading-dashboard-v2"
echo "✅ Service installed!"

# Step 5: Restart service
echo ""
echo "[5/6] Restarting dashboard service..."
ssh $SERVER "sudo systemctl restart trading-dashboard-v2"
sleep 3
echo "✅ Service restarted!"

# Step 6: Verify deployment
echo ""
echo "[6/6] Verifying deployment..."
ssh $SERVER "sudo systemctl status trading-dashboard-v2 --no-pager | head -20"

echo ""
echo "Testing HTTP endpoint..."
HTTP_CODE=$(curl -u admin:admin -s -o /dev/null -w "%{http_code}" http://192.168.178.55:9001)
if [ "$HTTP_CODE" == "200" ]; then
    echo "✅ Dashboard is accessible!"
else
    echo "⚠️  Dashboard returned HTTP $HTTP_CODE"
fi

echo ""
echo "===================================================="
echo "✅ Deployment Complete!"
echo "===================================================="
echo "Dashboard URL: http://192.168.178.55:9001"
echo "Username: admin"
echo "Password: admin"
echo ""
echo "View logs: ssh $SERVER 'sudo journalctl -u trading-dashboard-v2 -f'"
echo "===================================================="
