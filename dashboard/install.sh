#!/bin/bash
# Installation script for Trading System Status Dashboard
# Usage: sudo ./install.sh

set -e

echo "=========================================="
echo "Trading System Status Dashboard Installer"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run with sudo: sudo ./install.sh"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo ""
echo "Step 1: Adding $ACTUAL_USER to systemd-journal group..."
usermod -a -G systemd-journal "$ACTUAL_USER"
echo "✓ User added to systemd-journal group"

echo ""
echo "Step 2: Installing systemd service..."
# Update paths in service file to match current location
sed "s|/opt/trading/traderunner/dashboard|$SCRIPT_DIR|g" "$SCRIPT_DIR/trading-dashboard.service" > /tmp/trading-dashboard.service
sed -i "s|User=mirko|User=$ACTUAL_USER|g" /tmp/trading-dashboard.service
cp /tmp/trading-dashboard.service /etc/systemd/system/
rm /tmp/trading-dashboard.service
systemctl daemon-reload
echo "✓ Service file installed with paths:"
echo "  WorkingDirectory: $SCRIPT_DIR"
echo "  User: $ACTUAL_USER"

echo ""
echo "Step 3: Enabling and starting service..."
systemctl enable trading-dashboard
systemctl restart trading-dashboard
sleep 2
echo "✓ Service enabled and started"

echo ""
echo "Step 4: Verifying installation..."
if systemctl is-active --quiet trading-dashboard; then
    echo "✓ Service is running"
else
    echo "✗ Service failed to start"
    echo "Check logs with: journalctl -u trading-dashboard -n 50"
    exit 1
fi

# Test API endpoint
echo ""
echo "Step 5: Testing API endpoint..."
if curl -s http://localhost:9000/api/status > /dev/null 2>&1; then
    echo "✓ API endpoint responding"
else
    echo "⚠ API endpoint not responding (may need a moment to start)"
fi

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Dashboard URL: http://localhost:9000"
echo ""
echo "Useful commands:"
echo "  - View logs:    journalctl -u trading-dashboard -f"
echo "  - Restart:      sudo systemctl restart trading-dashboard"
echo "  - Stop:         sudo systemctl stop trading-dashboard"
echo "  - Status:       systemctl status trading-dashboard"
echo ""
echo "NOTE: $ACTUAL_USER needs to log out and back in for"
echo "      group changes to take effect."
echo ""
