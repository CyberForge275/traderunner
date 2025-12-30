#!/bin/bash
#
# Rollback script - restore previous version

set -e

BACKUP_DIR="/opt/trading/backups"
DEPLOY_DIR="/opt/trading"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Get backup to restore
BACKUP_TO_RESTORE="$1"

if [ -z "$BACKUP_TO_RESTORE" ]; then
    # Use latest backup
    BACKUP_TO_RESTORE=$(cat "$BACKUP_DIR/latest_backup.txt" 2>/dev/null || echo "")
    if [ -z "$BACKUP_TO_RESTORE" ]; then
        error "No backup specified and no latest backup found!"
        echo "Usage: $0 [timestamp]"
        echo "Available backups:"
        ls -1 "$BACKUP_DIR"/*.tar.gz 2>/dev/null | sed 's/.*_\([0-9_]*\).tar.gz/\1/' || echo "None"
        exit 1
    fi
    log "Using latest backup: $BACKUP_TO_RESTORE"
fi

log "========================================="
log "Starting rollback to $BACKUP_TO_RESTORE..."
log "=========================================\n"

# Stop services
log "Stopping services..."
sudo systemctl stop automatictrader-api || true
sudo systemctl stop automatictrader-worker || true

# Restore backups
if [ -f "$BACKUP_DIR/automatictrader-api_${BACKUP_TO_RESTORE}.tar.gz" ]; then
    log "Restoring automatictrader-api..."
    tar xzf "$BACKUP_DIR/automatictrader-api_${BACKUP_TO_RESTORE}.tar.gz" -C "$DEPLOY_DIR"
    log "✓ Restored automatictrader-api"
else
    error "Backup file not found: automatictrader-api_${BACKUP_TO_RESTORE}.tar.gz"
fi

if [ -f "$BACKUP_DIR/traderunner_${BACKUP_TO_RESTORE}.tar.gz" ]; then
    log "Restoring traderunner..."
    tar xzf "$BACKUP_DIR/traderunner_${BACKUP_TO_RESTORE}.tar.gz" -C "$DEPLOY_DIR"
    log "✓ Restored traderunner"
else
    error "Backup file not found: traderunner_${BACKUP_TO_RESTORE}.tar.gz"
fi

# Restart services
log "Starting services..."
sudo systemctl start automatictrader-api || true
sudo systemctl start automatictrader-worker || true

sleep 3

# Health check
log "Running health check..."
if curl -sf http://localhost:8080/healthz > /dev/null; then
    log "✓ automatictrader-api is healthy"
else
    error "Health check failed after rollback!"
    exit 1
fi

log "\n========================================="
log "✅ Rollback successful!"
log "=========================================\n"
