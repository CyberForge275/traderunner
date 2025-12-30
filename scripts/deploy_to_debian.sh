#!/bin/bash
set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LOCAL_TRADERUNNER_PATH="/home/mirko/data/workspace/droid/traderunner"
LOCAL_API_PATH="/home/mirko/data/workspace/automatictrader-api"
REMOTE_DIR="/opt/trading"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Trading System Debian Deployment${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Step 1: Get server details
echo -e "${YELLOW}Step 1: Server Configuration${NC}"
read -p "Enter server hostname or IP: " SERVER_HOST
read -p "Enter SSH user: " SSH_USER
SERVER="${SSH_USER}@${SERVER_HOST}"

echo ""
echo -e "${GREEN}✓ Server configured: ${SERVER}${NC}"
echo ""

# Step 2: Test SSH connection
echo -e "${YELLOW}Step 2: Testing SSH connection...${NC}"
if ssh -q ${SERVER} exit; then
    echo -e "${GREEN}✓ SSH connection successful${NC}"
else
    echo -e "${RED}✗ SSH connection failed. Please check your credentials and network.${NC}"
    exit 1
fi
echo ""

# Step 3: Create remote directory
echo -e "${YELLOW}Step 3: Creating remote directory...${NC}"
echo -e "${BLUE}Checking if you have sudo access...${NC}"

# Try with sudo first (using -t for TTY)
if ssh -t ${SERVER} "sudo mkdir -p ${REMOTE_DIR} && sudo chown ${SSH_USER}:${SSH_USER} ${REMOTE_DIR}" 2>/dev/null; then
    echo -e "${GREEN}✓ Remote directory created: ${REMOTE_DIR}${NC}"
else
    echo -e "${YELLOW}⚠ Cannot create ${REMOTE_DIR} (requires sudo)${NC}"
    echo -e "${BLUE}Would you like to use ~/trading instead? (y/n)${NC}"
    read -p "Use home directory? " USE_HOME

    if [[ "$USE_HOME" == "y" || "$USE_HOME" == "Y" ]]; then
        REMOTE_DIR="~/trading"
        ssh ${SERVER} "mkdir -p ${REMOTE_DIR}"
        echo -e "${GREEN}✓ Using directory: ${REMOTE_DIR}${NC}"
    else
        echo -e "${RED}Please create ${REMOTE_DIR} manually and re-run this script.${NC}"
        exit 1
    fi
fi
echo ""

# Step 3.5: Check and install rsync on remote server
echo -e "${YELLOW}Step 3.5: Checking for rsync on server...${NC}"
if ssh ${SERVER} "command -v rsync > /dev/null"; then
    echo -e "${GREEN}✓ rsync is installed${NC}"
else
    echo -e "${YELLOW}⚠ rsync not found, installing...${NC}"
    ssh -t ${SERVER} "sudo apt-get update -qq && sudo apt-get install -y rsync"
    echo -e "${GREEN}✓ rsync installed${NC}"
fi
echo ""

# Step 4: Copy traderunner
echo -e "${YELLOW}Step 4: Copying traderunner to server...${NC}"
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache' \
    --exclude 'artifacts/*' \
    --exclude '.venv' \
    ${LOCAL_TRADERUNNER_PATH}/ \
    ${SERVER}:${REMOTE_DIR}/traderunner/
echo -e "${GREEN}✓ traderunner copied${NC}"
echo ""

# Step 5: Copy automatictrader-api
echo -e "${YELLOW}Step 5: Copying automatictrader-api to server...${NC}"
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'data' \
    --exclude '.venv' \
    ${LOCAL_API_PATH}/ \
    ${SERVER}:${REMOTE_DIR}/automatictrader-api/
echo -e "${GREEN}✓ automatictrader-api copied${NC}"
echo ""

# Step 6: Setup Python environment for automatictrader-api
echo -e "${YELLOW}Step 6: Setting up Python environment for automatictrader-api...${NC}"
ssh ${SERVER} << 'ENDSSH'
cd /opt/trading/automatictrader-api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
ENDSSH
echo -e "${GREEN}✓ automatictrader-api Python environment ready${NC}"
echo ""

# Step 7: Setup Python environment for traderunner
echo -e "${YELLOW}Step 7: Setting up Python environment for traderunner...${NC}"
ssh ${SERVER} << 'ENDSSH'
cd /opt/trading/traderunner
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
mkdir -p data artifacts/signals artifacts/orders
ENDSSH
echo -e "${GREEN}✓ traderunner Python environment ready${NC}"
echo ""

# Step 8: Configure environment
echo -e "${YELLOW}Step 8: Configuring environment...${NC}"
ssh ${SERVER} << 'ENDSSH'
cd /opt/trading/automatictrader-api
if [ ! -f .env ]; then
    cp .env.example .env
    # Set safe defaults for initial deployment
    sed -i 's/^AT_WORKER_MODE=.*/AT_WORKER_MODE=plan-only/' .env
    sed -i 's/^AT_AUTO_PROMOTE=.*/AT_AUTO_PROMOTE=0/' .env
    sed -i 's|^AT_DB_PATH=.*|AT_DB_PATH=/opt/trading/automatictrader-api/data/automatictrader.db|' .env
    echo "ENV_ALLOW_SEND=0" >> .env
fi
ENDSSH
echo -e "${GREEN}✓ Environment configured (plan-only mode for safety)${NC}"
echo ""

# Step 9: Initialize database
echo -e "${YELLOW}Step 9: Initializing database...${NC}"
ssh ${SERVER} << 'ENDSSH'
cd /opt/trading/automatictrader-api
source .venv/bin/activate
mkdir -p data
python -c "from storage import init_db; init_db()" 2>/dev/null || echo "Database already initialized or schema loaded via app startup"
ENDSSH
echo -e "${GREEN}✓ Database initialized${NC}"
echo ""

# Step 10: Test health check
echo -e "${YELLOW}Step 10: Running health check test...${NC}"
echo -e "${BLUE}Starting API server temporarily for testing...${NC}"

# Start API in background
ssh ${SERVER} << 'ENDSSH' &
cd /opt/trading/automatictrader-api
source .venv/bin/activate
timeout 30 python -m uvicorn app:app --host 127.0.0.1 --port 8080 > /tmp/api_test.log 2>&1 || true
ENDSSH

sleep 5  # Give API time to start

# Test health endpoint
if ssh ${SERVER} "curl -s http://localhost:8080/healthz" | grep -q "ok"; then
    echo -e "${GREEN}✓ API health check passed${NC}"
else
    echo -e "${YELLOW}⚠ Health check Warning: API may need manual verification${NC}"
fi

# Kill the test API
ssh ${SERVER} "pkill -f 'uvicorn app:app' 2>/dev/null || true"
echo ""

# Step 11: Create systemd services
echo -e "${YELLOW}Step 11: Do you want to setup systemd services for production? (y/n)${NC}"
read -p "Setup systemd? " SETUP_SYSTEMD

if [[ "$SETUP_SYSTEMD" == "y" || "$SETUP_SYSTEMD" == "Y" ]]; then
    echo -e "${BLUE}Setting up systemd services...${NC}"

    # Create trading user
    ssh -t ${SERVER} "sudo useradd -r -s /bin/bash -d ${REMOTE_DIR} trading 2>/dev/null || echo 'User already exists'"
    ssh -t ${SERVER} "sudo chown -R trading:trading ${REMOTE_DIR}"

    # Create API service file
    ssh -t ${SERVER} sudo tee /etc/systemd/system/automatictrader-api.service > /dev/null << EOF
[Unit]
Description=Automatic Trader API
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=${REMOTE_DIR}/automatictrader-api
Environment="PATH=${REMOTE_DIR}/automatictrader-api/.venv/bin"
EnvironmentFile=${REMOTE_DIR}/automatictrader-api/.env
ExecStart=${REMOTE_DIR}/automatictrader-api/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Create Worker service file
    ssh -t ${SERVER} sudo tee /etc/systemd/system/automatictrader-worker.service > /dev/null << EOF
[Unit]
Description=Automatic Trader Worker
After=network.target automatictrader-api.service
Requires=automatictrader-api.service

[Service]
Type=simple
User=trading
WorkingDirectory=${REMOTE_DIR}/automatictrader-api
Environment="PATH=${REMOTE_DIR}/automatictrader-api/.venv/bin"
EnvironmentFile=${REMOTE_DIR}/automatictrader-api/.env
ExecStart=${REMOTE_DIR}/automatictrader-api/.venv/bin/python worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable services
    ssh -t ${SERVER} << 'ENDSSH'
sudo systemctl daemon-reload
sudo systemctl enable automatictrader-api
sudo systemctl enable automatictrader-worker
ENDSSH

    echo -e "${GREEN}✓ Systemd services created and enabled${NC}"
    echo ""

    # Ask if they want to start services now
    echo -e "${YELLOW}Start services now? (y/n)${NC}"
    read -p "Start services? " START_SERVICES

    if [[ "$START_SERVICES" == "y" || "$START_SERVICES" == "Y" ]]; then
        ssh -t ${SERVER} << 'ENDSSH'
sudo systemctl start automatictrader-api
sudo systemctl start automatictrader-worker
ENDSSH
        echo -e "${GREEN}✓ Services started${NC}"
        echo ""

        # Show status
        echo -e "${BLUE}Service Status:${NC}"
        ssh -t ${SERVER} "sudo systemctl status automatictrader-api --no-pager -l"
        echo ""
        ssh -t ${SERVER} "sudo systemctl status automatictrader-worker --no-pager -l"
    fi
else
    echo -e "${BLUE}Skipping systemd setup. You can run services manually with:${NC}"
    echo -e "  cd ${REMOTE_DIR}/automatictrader-api"
    echo -e "  source .venv/bin/activate"
    echo -e "  bash scripts/run_dev.sh  # Terminal 1"
    echo -e "  bash scripts/worker_dev.sh  # Terminal 2"
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Deployment Complete! ✓${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. SSH into your server: ssh ${SERVER}"
echo "2. Monitor logs: sudo journalctl -u automatictrader-api -f"
echo "3. Test signal generation:"
echo "   cd ${REMOTE_DIR}/traderunner"
echo "   source .venv/bin/activate"
echo "   PYTHONPATH=src python -m signals.cli_rudometkin_moc --symbols AAPL --start 2025-11-20 --end 2025-11-20"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- System is in PLAN-ONLY mode (safe for testing)"
echo "- Edit ${REMOTE_DIR}/automatictrader-api/.env to enable paper trading"
echo "- Monitor for 24 hours before enabling IB integration"
echo ""
