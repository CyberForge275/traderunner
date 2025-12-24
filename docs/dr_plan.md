# Disaster Recovery Plan (v2)

## Overview
This document defines the disaster recovery (DR) strategy for the traderunner trading system.

**Objectives:**
- **RTO (Recovery Time Objective):** 15 minutes
- **RPO (Recovery Point Objective):** 5 minutes

---

## Critical Assets

### 1. **Configuration Files**
- Location: `configs/`
- Criticality: HIGH
- Backup: Git + hourly snapshots
- Recovery: Git checkout

### 2. **Historical Data**
- Location: `data/` and `artifacts/data_m1/`, `artifacts/data_m5/`
- Criticality: MEDIUM (can re-fetch)
- Backup: Daily to restic
- Recovery: Restore from backup or re-fetch

### 3. **Strategy Code**
- Location: `src/`
- Criticality: HIGH
- Backup: Git
- Recovery: Git checkout

### 4. **Run Artifacts**
- Location: `artifacts/backtests/`, `artifacts/state/`
- Criticality: MEDIUM (reproducible)
- Backup: Weekly to restic
- Recovery: Restore or re-run

### 5. **Live Trading State**
- Location: `artifacts/state/` (positions, orders, P&L)
- Criticality: CRITICAL
- Backup: Real-time to separate disk + cloud
- Recovery: Restore latest + reconcile with broker

---

## Backup Strategy

### Git-based Backups (Code & Config)
```bash
# Automatic via GitHub
git push origin main
git push origin --tags

# All branches backed up to remote
```

### File-based Backups (Data & Artifacts)
```bash
# Using restic for incremental backups

# Initialize backup repository (one-time)
restic -r /backup/traderunner init

# Daily backup (via cron)
restic -r /backup/traderunner backup \
    /home/mirko/data/workspace/droid/traderunner/data \
    /home/mirko/data/workspace/droid/traderunner/artifacts \
    /home/mirko/data/workspace/droid/traderunner/configs

# Cloud backup (optional)
restic -r s3:s3.amazonaws.com/traderunner-backup backup ...
```

### State Backups (Live Trading)
```bash
# Real-time state backup (every minute during live trading)
while true; do
    cp artifacts/state/*.json /backup/state/$(date +%Y%m%d-%H%M%S)/
    sleep 60
done
```

---

## Recovery Procedures

### Scenario 1: Code/Config Corruption
**Symptoms:**
- Application won't start
- Import errors
- Config parsing errors

**Recovery:**
```bash
# 1. Navigate to repository
cd /home/mirko/data/workspace/droid/traderunner

# 2. Check for uncommitted changes
git status

# 3. Restore from stable tag
git checkout v1.0-stable

# 4. Verify
make test
make health-check

# 5. If still broken, re-clone
cd /home/mirko/data/workspace/droid/
mv traderunner traderunner.broken
git clone https://github.com/CyberForge275/traderunner.git
cd traderunner
git checkout v1.0-stable
```

**RTO:** < 5 minutes

---

### Scenario 2: Data Corruption
**Symptoms:**
- Parquet read errors
- Data validation failures
- SLA violations

**Recovery:**
```bash
# 1. Identify corrupted files
make data:validate

# 2. Option A: Restore from backup
restic -r /backup/traderunner restore latest \
    --target /tmp/restore \
    --path /home/mirko/data/workspace/droid/traderunner/data

cp -r /tmp/restore/data/* data/

# 3. Option B: Re-fetch from source
make data:fetch START_DATE=2024-01-01 END_DATE=2024-12-31

# 4. Verify
make data:validate
```

**RTO:** < 10 minutes (Option A), < 30 minutes (Option B)

---

### Scenario 3: Live Trading System Failure
**Symptoms:**
- Broker connection lost
- System crash during live trading
- Unexpected shutdown

**Recovery:**
```bash
# CRITICAL: First action - verify live positions

# 1. Log into broker (IBKR TWS)
# - Check actual positions
# - Note any pending orders

# 2. Compare with system state
cat artifacts/state/positions.json
cat artifacts/state/pending_orders.json

# 3. Restore latest state
restic -r /backup/traderunner snapshots
restic -r /backup/traderunner restore <snapshot-id> \
    --target /tmp/restore \
    --path artifacts/state

# 4. Reconcile discrepancies
# - Manual: Update positions.json to match broker
# - Or: Run reconciliation script (TODO)

# 5. Restart system
git checkout v1.0-stable
TR_MODE=live make start

# 6. Verify positions match
make verify:positions
```

**RTO:** < 15 minutes

---

### Scenario 4: Complete Server Failure
**Symptoms:**
- Server unreachable
- Hardware failure
- Data center outage

**Recovery (to Backup Server):**
```bash
# 1. On backup server, clone repository
ssh backup-server
cd /opt/trading
git clone https://github.com/CyberForge275/traderunner.git
cd traderunner

# 2. Restore data from cloud backup
restic -r s3:s3.amazonaws.com/traderunner-backup snapshots
restic -r s3:s3.amazonaws.com/traderunner-backup restore latest \
    --target .

# 3. Install dependencies
pip install -r requirements.txt

# 4. Restore environment variables
# - IBKR credentials
# - API keys
# - Config overrides

# 5. Reconcile with broker
# - Verify positions
# - Cancel stale orders

# 6. Start in safe mode (manual approval required)
TR_MODE=paper make start

# 7. Once verified, switch to live
TR_MODE=live make start
```

**RTO:** < 30 minutes

---

## Environment Switching

### Switch to Paper Trading (Safe Mode)
```bash
# Environment variable
export TR_MODE=paper

# Verify
make health-check

# Should show: "Mode: PAPER"
```

### Switch to Live Trading
```bash
# Environment variable
export TR_MODE=live

# Verify (manual checks required)
make health-check
make verify:broker-connection
make verify:positions
```

---

## Rollback Strategy

### Git-based Rollback
```bash
# 1. Identify last stable version
git tag -l | grep stable

# 2. Checkout stable tag
git checkout v1.0-stable

# 3. Or rollback specific commits
git log --oneline -10
git revert <commit-hash>
```

### Config Rollback
```bash
# Configs are versioned in Git
git log configs/risk.yml
git checkout HEAD~1 -- configs/risk.yml
```

### Deploy Rollback
```bash
# If deployed to production, rollback
# TODO: Document deployment process
# For now: manual git checkout + restart
```

---

## Testing DR Plan

### Quarterly DR Drills

**Q1 Drill: Data Corruption**
- Simulate: Delete data_m5/ directory
- Restore from backup
- Verify: Data SLAs pass
- Measure: RTO achieved?

**Q2 Drill: Config Corruption**
- Simulate: Corrupt configs/risk.yml
- Restore from Git
- Verify: System starts successfully
- Measure: RTO < 5 min?

**Q3 Drill: Live Trading Failure**
- Simulate: Kill live trading process
- Restore state
- Reconcile with broker
- Verify: Positions match
- Measure: RTO < 15 min?

**Q4 Drill: Complete Server Failure**
- Simulate: Fail over to backup server
- Restore from cloud
- Start in paper mode
- Switch to live after verification
- Measure: RTO < 30 min?

---

## Checklist: Post-Disaster

After any disaster recovery:
- [ ] Document incident (what/when/why)
- [ ] Update DR plan with learnings
- [ ] Review RTO/RPO metrics
- [ ] Test restored system thoroughly
- [ ] Notify stakeholders
- [ ] Schedule postmortem

---

## Contacts

**Infrastructure:**
- Primary: [Contact]
- Secondary: [Contact]

**Broker Support:**
- IBKR: [Phone/Email]

**Cloud Provider:**
- AWS/DigitalOcean: [Support]

---

**RTO/RPO Summary:**

| Scenario | RTO Target | Actual | RPO Target | Actual |
|----------|-----------|--------|-----------|--------|
| Code corruption | 5 min | - | 0 min | - |
| Data corruption | 10 min | - | 5 min | - |
| Live system failure | 15 min | - | 1 min | - |
| Complete server failure | 30 min | - | 5 min | - |

*Update "Actual" after each drill or real incident*

---

**Last Updated:** 2025-11-27
**Next Review:** 2026-02-27
**Last Tested:** TBD
**Owner:** Trading Team
