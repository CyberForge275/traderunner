#!/bin/bash
#
# Deployment script for trading system on Debian server
# Executed by GitHub Actions or manually

set -e  # Exit on error

LOG_FILE="/var/log/trading/deploy.log"
BACKUP_DIR="/opt/trading/backups"
DEPLOY_DIR="/opt/trading"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

# Create backup
backup() {
    log "Creating backup..."
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    mkdir -p "$BACKUP_DIR"

    # Backup automatictrader-api
    if [ -d "$DEPLOY_DIR/automatictrader-api" ]; then
        tar czf "$BACKUP_DIR/automatictrader-api_${TIMESTAMP}.tar.gz" \
            -C "$DEPLOY_DIR" automatictrader-api
        log "✓ Backed up automatictrader-api"
    fi

    # Backup traderunner
    if [ -d "$DEPLOY_DIR/traderunner" ]; then
        tar czf "$BACKUP_DIR/traderunner_${TIMESTAMP}.tar.gz" \
            -C "$DEPLOY_DIR" traderunner
        log "✓ Backed up traderunner"
    fi

    # Keep only last 10 backups
    ls -t "$BACKUP_DIR"/*.tar.gz | tail -n +11 | xargs -r rm

    echo "$TIMESTAMP" > "$BACKUP_DIR/latest_backup.txt"
}

# Pull latest code
pull_code() {
    log "Pulling latest code..."

    cd "$DEPLOY_DIR/automatictrader-api"
    git pull origin main
    log "✓ Updated automatictrader-api"

    cd "$DEPLOY_DIR/traderunner"
    git pull origin main
    log "✓ Updated traderunner"
}

# Install dependencies
install_deps() {
    log "Installing dependencies..."

    # automatictrader-api
    cd "$DEPLOY_DIR/automatictrader-api"
    if [ -f "requirements.txt" ]; then
        python3 -m pip install -q -r requirements.txt
        log "✓ Installed automatictrader-api dependencies"
    fi

    # traderunner
    cd "$DEPLOY_DIR/traderunner"
    if [ -f "requirements.txt" ]; then
        python3 -m pip install -q -r requirements.txt
        log "✓ Installed traderunner dependencies"
    fi
}

# Restart services
restart_services() {
    log "Restarting services..."

    # Check if services exist before restarting
    if systemctl list-units --full -all | grep -q "automatictrader-api.service"; then
        sudo systemctl restart automatictrader-api
        log "✓ Restarted automatictrader-api"
    else
        warn "automatictrader-api service not found"
    fi

    if systemctl list-units --full -all | grep -q "automatictrader-worker.service"; then
        sudo systemctl restart automatictrader-worker
        log "✓ Restarted automatictrader-worker"
    else
        warn "automatictrader-worker service not found"
    fi

    # Wait for services to start
    sleep 3
}

# Health check
health_check() {
    log "Running health checks..."

    # Check automatictrader-api
    if curl -sf http://localhost:8080/healthz > /dev/null; then
        log "✓ automatictrader-api is healthy"
    else
        error "automatictrader-api health check failed!"
        return 1
    fi

    #  Check Prometheus
    if curl -sf http://localhost:9090/-/healthy > /dev/null; then
        log "✓ Prometheus is healthy"
    else
        warn "Prometheus health check failed (may not be running)"
    fi

    return 0
}

# Rollback on failure
rollback() {
    error "Deployment failed! Rolling back..."

    LATEST_BACKUP=$(cat "$BACKUP_DIR/latest_backup.txt" 2>/dev/null || echo "")

    if [ -z "$LATEST_BACKUP" ]; then
        error "No backup found for rollback!"
        return 1
    fi

    log "Restoring backup from $LATEST_BACKUP..."

    # Stop services
    sudo systemctl stop automatictrader-api || true
    sudo systemctl stop automatictrader-worker || true

    # Restore backups
    if [ -f "$BACKUP_DIR/automatictrader-api_${LATEST_BACKUP}.tar.gz" ]; then
        tar xzf "$BACKUP_DIR/automatictrader-api_${LATEST_BACKUP}.tar.gz" -C "$DEPLOY_DIR"
        log "✓ Restored automatictrader-api"
    fi

    if [ -f "$BACKUP_DIR/traderunner_${LATEST_BACKUP}.tar.gz" ]; then
        tar xzf "$BACKUP_DIR/traderunner_${LATEST_BACKUP}.tar.gz" -C "$DEPLOY_DIR"
        log "✓ Restored traderunner"
    fi

    # Restart services
    sudo systemctl start automatictrader-api || true
    sudo systemctl start automatictrader-worker || true

    log "Rollback complete"
}

# Main deployment flow
main() {
    log "========================================="
    log "Starting deployment..."
    log "=========================================\n"

    # Backup current version
    backup || { error "Backup failed!"; exit 1; }

    # Pull latest code
    pull_code || { error "Git pull failed!"; rollback; exit 1; }

    # Install dependencies
    install_deps || { error "Dependency installation failed!"; rollback; exit 1; }

    # Restart services
    restart_services || { warn "Service restart had issues"; }

    # Health check
    if health_check; then
        log "\n========================================="
        log "✅ Deployment successful!"
        log "=========================================\n"
        exit 0
    else
        error "Health check failed!"
        rollback
        exit 1
    fi
}

# Run main deployment
main
