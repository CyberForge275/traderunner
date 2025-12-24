#!/bin/bash
# Deployment Sanity Check Script
# Run this on the Debian server after deployment to verify everything is working

# Don't exit on errors - we want to run all checks
set +e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Deployment paths
DEPLOY_DIR="/opt/trading"
API_DIR="${DEPLOY_DIR}/automatictrader-api"
RUNNER_DIR="${DEPLOY_DIR}/traderunner"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Trading System Deployment Sanity Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Helper functions
check_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
    ((WARNINGS++))
}

# Test 1: Directory Structure
echo -e "${BLUE}[1/12] Checking directory structure...${NC}"
if [ -d "$DEPLOY_DIR" ]; then
    check_pass "Deployment directory exists: $DEPLOY_DIR"
else
    check_fail "Deployment directory missing: $DEPLOY_DIR"
fi

if [ -d "$API_DIR" ]; then
    check_pass "API directory exists: $API_DIR"
else
    check_fail "API directory missing: $API_DIR"
fi

if [ -d "$RUNNER_DIR" ]; then
    check_pass "TradeRunner directory exists: $RUNNER_DIR"
else
    check_fail "TradeRunner directory missing: $RUNNER_DIR"
fi
echo ""

# Test 2: Python Virtual Environments
echo -e "${BLUE}[2/12] Checking Python virtual environments...${NC}"
if [ -d "$API_DIR/.venv" ]; then
    check_pass "API virtual environment exists"
else
    check_fail "API virtual environment missing"
fi

if [ -d "$RUNNER_DIR/.venv" ]; then
    check_pass "TradeRunner virtual environment exists"
else
    check_fail "TradeRunner virtual environment missing"
fi
echo ""

# Test 3: Required Files
echo -e "${BLUE}[3/12] Checking required files...${NC}"
declare -a api_files=("app.py" "worker.py" "storage.py" "requirements.txt")
for file in "${api_files[@]}"; do
    if [ -f "$API_DIR/$file" ]; then
        check_pass "API file exists: $file"
    else
        check_fail "API file missing: $file"
    fi
done

declare -a runner_files=("requirements.txt" "README.md")
for file in "${runner_files[@]}"; do
    if [ -f "$RUNNER_DIR/$file" ]; then
        check_pass "TradeRunner file exists: $file"
    else
        check_fail "TradeRunner file missing: $file"
    fi
done
echo ""

# Test 4: Configuration Files
echo -e "${BLUE}[4/12] Checking configuration...${NC}"
if [ -f "$API_DIR/.env" ]; then
    check_pass ".env file exists"
    
    # Check critical settings
    if grep -q "AT_WORKER_MODE" "$API_DIR/.env"; then
        MODE=$(grep "AT_WORKER_MODE" "$API_DIR/.env" | cut -d'=' -f2 | tr -d '"' | tr -d ' ')
        if [ "$MODE" = "plan-only" ]; then
            check_pass "Worker mode is SAFE: $MODE"
        elif [ "$MODE" = "paper-send" ]; then
            check_warn "Worker mode is LIVE PAPER SENDING: $MODE"
        else
            check_warn "Worker mode unknown: $MODE"
        fi
    else
        check_warn "AT_WORKER_MODE not set in .env"
    fi
    
    if grep -q "ENV_ALLOW_SEND" "$API_DIR/.env"; then
        SEND=$(grep "ENV_ALLOW_SEND" "$API_DIR/.env" | cut -d'=' -f2 | tr -d '"' | tr -d ' ')
        if [ "$SEND" = "0" ]; then
            check_pass "Sending is DISABLED (safe)"
        else
            check_warn "Sending is ENABLED: ENV_ALLOW_SEND=$SEND"
        fi
    fi
else
    check_fail ".env file missing"
fi
echo ""

# Test 5: Data Directories
echo -e "${BLUE}[5/12] Checking data directories...${NC}"
if [ -d "$API_DIR/data" ]; then
    check_pass "API data directory exists"
else
    check_warn "API data directory missing (will be created on first run)"
    mkdir -p "$API_DIR/data" 2>/dev/null && check_pass "Created data directory"
fi

if [ -d "$RUNNER_DIR/artifacts" ]; then
    check_pass "TradeRunner artifacts directory exists"
else
    check_warn "TradeRunner artifacts directory missing"
fi
echo ""

# Test 6: Python Dependencies - API
echo -e "${BLUE}[6/12] Checking API Python dependencies...${NC}"
cd "$API_DIR"
source .venv/bin/activate

declare -a api_deps=("fastapi" "uvicorn" "pydantic" "sqlite3")
for dep in "${api_deps[@]}"; do
    if python -c "import $dep" 2>/dev/null; then
        check_pass "Python module available: $dep"
    else
        if [ "$dep" = "sqlite3" ]; then
            # sqlite3 might not import directly, check differently
            if python -c "import sqlite3" 2>/dev/null; then
                check_pass "Python module available: sqlite3"
            else
                check_fail "Python module missing: $dep"
            fi
        else
            check_fail "Python module missing: $dep"
        fi
    fi
done
deactivate
echo ""

# Test 7: Python Dependencies - TradeRunner
echo -e "${BLUE}[7/12] Checking TradeRunner Python dependencies...${NC}"
cd "$RUNNER_DIR"
source .venv/bin/activate

declare -a runner_deps=("pandas" "numpy" "streamlit")
for dep in "${runner_deps[@]}"; do
    if python -c "import $dep" 2>/dev/null; then
        check_pass "Python module available: $dep"
    else
        check_fail "Python module missing: $dep"
    fi
done
deactivate
echo ""

# Test 8: Database
echo -e "${BLUE}[8/12] Checking database...${NC}"
DB_PATH="$API_DIR/data/automatictrader.db"
if [ -f "$DB_PATH" ]; then
    check_pass "Database file exists: $DB_PATH"
    
    # Check tables
    TABLES=$(sqlite3 "$DB_PATH" ".tables" 2>/dev/null || echo "")
    if [ -n "$TABLES" ]; then
        check_pass "Database has tables: $TABLES"
    else
        check_warn "Database exists but has no tables (will be initialized on first run)"
    fi
else
    check_warn "Database not initialized yet (will be created on first run)"
fi
echo ""

# Test 9: Port Availability
echo -e "${BLUE}[9/12] Checking port availability...${NC}"
if ! lsof -i :8080 >/dev/null 2>&1; then
    check_pass "Port 8080 is available"
else
    check_warn "Port 8080 is in use (API may already be running)"
fi
echo ""

# Test 10: API Startup Test
echo -e "${BLUE}[10/12] Testing API startup...${NC}"
cd "$API_DIR"
source .venv/bin/activate

# Try to import the app
if python -c "from app import app; print('OK')" 2>/dev/null | grep -q "OK"; then
    check_pass "API app imports successfully"
else
    check_fail "API app has import errors"
fi
deactivate
echo ""

# Test 11: Worker Startup Test
echo -e "${BLUE}[11/12] Testing worker...${NC}"
cd "$API_DIR"
source .venv/bin/activate

# Check if worker imports correctly
if python -c "import worker; print('OK')" 2>/dev/null | grep -q "OK"; then
    check_pass "Worker imports successfully"
else
    check_fail "Worker has import errors"
fi
deactivate
echo ""

# Test 12: Signal Generation Test
echo -e "${BLUE}[12/12] Testing signal generation...${NC}"
cd "$RUNNER_DIR"
source .venv/bin/activate

# Test if signal CLI can be imported
if python -c "import sys; sys.path.insert(0, 'src'); from signals.cli_rudometkin_moc import main; print('OK')" 2>/dev/null | grep -q "OK"; then
    check_pass "Signal generation module imports successfully"
else
    check_warn "Signal generation module has import issues (may need data files)"
fi
deactivate
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Passed:   $PASSED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo -e "${RED}Failed:   $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment sanity check PASSED!${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Start the API: cd $API_DIR && source .venv/bin/activate && python -m uvicorn app:app --host 127.0.0.1 --port 8080"
    echo "2. Start the worker: cd $API_DIR && source .venv/bin/activate && python worker.py"
    echo "3. Generate signals: cd $RUNNER_DIR && source .venv/bin/activate && PYTHONPATH=src python -m signals.cli_rudometkin_moc --symbols AAPL --start 2025-11-20 --end 2025-11-20"
    exit 0
else
    echo -e "${RED}✗ Deployment sanity check FAILED!${NC}"
    echo ""
    echo "Please fix the failed checks before proceeding."
    exit 1
fi
