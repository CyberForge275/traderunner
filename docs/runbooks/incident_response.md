# Incident Response Runbook

## Purpose
This runbook provides step-by-step procedures for responding to incidents during paper and live trading.

---

## Severity Levels

### **P0 - Critical**
- Live trading system down
- Data corruption
- Kill switch triggered
- Unexpected position liquidation

### **P1 - High**
- Paper trading system down
- High latency (> p99 SLO)
- Order rejections > 10%
- SLA violations

### **P2 - Medium**
- Dashboard unavailable
- Metrics collection failing
- Non-critical errors in logs

### **P3 - Low**
- Performance degradation
- Documentation updates needed

---

## Emergency Contacts

**Trading Team:**
- Primary: [Contact Info]
- Secondary: [Contact Info]

**Infrastructure:**
- DevOps: [Contact Info]

**Broker Support:**
- IBKR: [Support Number]

---

## Incident Response Procedures

### 1. Kill Switch Triggered

**Symptoms:**
- Trading halted
- "Kill switch activated" in logs
- No new orders being sent

**Steps:**
1. **Verify trigger reason**
   ```bash
   cd /home/mirko/data/workspace/droid/traderunner
   grep "kill_switch" artifacts/logs/latest.log
   ```

2. **Check portfolio state**
   ```bash
   # Review open positions
   cat artifacts/state/positions.json

   # Check daily P&L
   cat artifacts/state/daily_pnl.json
   ```

3. **Decision point:**
   - If loss is within acceptable range → Investigate root cause
   - If loss exceeds limits → Keep kill switch active, escalate to P0

4. **Root cause analysis**
   - Review recent trades
   - Check for strategy bugs
   - Verify data quality

5. **Recovery**
   ```bash
   # Only reset after approval
   # TODO: Implement reset command
   ```

---

### 2. Broker Connection Lost

**Symptoms:**
- "Connection timeout" errors
- Orders not filling
- No market data updates

**Steps:**
1. **Check broker status**
   - Visit IBKR status page
   - Check network connectivity

2. **Attempt reconnection**
   ```bash
   # Restart broker connector
   # TODO: systemctl restart traderunner-broker
   ```

3. **Fallback**
   - If reconnection fails after 3 attempts → Manual intervention
   - Contact broker support

---

### 3. Data SLA Violation

**Symptoms:**
- Dashboard shows red SLA badge
- "SLA violation" in logs
- Incomplete M5 data

**Steps:**
1. **Identify violation**
   ```bash
   cat artifacts/quality/latest_sla.json
   ```

2. **Check data source**
   - EODHD API status
   - Network connectivity
   - Disk space

3. **Prevent promotion**
   - SLA violations block Paper/Live promotion
   - Fix data issues before proceeding

4. **Recovery**
   ```bash
   # Re-fetch data
   make data:fetch
   make data:validate
   ```

---

### 4. Unexpected Position

**Symptoms:**
- Position exists without corresponding order
- Size mismatch between expected and actual

**Steps:**
1. **Verify via broker**
   - Log into IBKR TWS/Dashboard
   - Check actual positions

2. **Compare with system state**
   ```bash
   diff artifacts/state/expected_positions.json \
        artifacts/state/actual_positions.json
   ```

3. **Idempotency check**
   ```bash
   # Check for duplicate order IDs
   grep "idempotency_key" artifacts/orders/*.csv | sort | uniq -d
   ```

4. **Reconciliation**
   - If position is valid → Update system state
   - If position is erroneous → Manual close via TWS

---

## Rollback Procedures

### Rollback to Stable Version

```bash
# 1. Stop current deployment
# TODO: systemctl stop traderunner

# 2. Checkout stable tag
git checkout v1.0-stable

# 3. Restore configuration
cp configs/backup/risk.yml.backup configs/risk.yml

# 4. Restart
# TODO: systemctl start traderunner

# 5. Verify
make health-check
```

### Rollback Paper → Lab

```bash
# Switch environment
export TR_MODE=lab

# Verify no live connections
# TODO: Check broker connections are disabled
```

---

## Post-Incident

### Required Actions
1. **Document incident**
   - Create issue in GitHub
   - Include timeline, root cause, resolution

2. **Update runbook**
   - Add new failure modes discovered
   - Update contact information

3. **Review metrics**
   - Analyze what monitoring caught/missed
   - Improve alerting

4. **Conduct postmortem**
   - Schedule within 48 hours
   - Share learnings with team

---

## Testing This Runbook

**Quarterly Drills:**
- Q1: Simulate kill switch trigger
- Q2: Simulate broker disconnection
- Q3: Simulate data corruption
- Q4: Full system failure drill

**Drill Checklist:**
- [ ] All team members know their roles
- [ ] Runbook steps are clear and actionable
- [ ] RTO (Recovery Time Objective) is met
- [ ] Lessons learned documented

---

**Last Updated:** 2025-11-27
**Next Review:** 2026-02-27
**Owner:** Trading Team
