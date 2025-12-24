# Promotion Checklist

## Purpose
Ensure safe and systematic promotion of strategies through stages:
`Experiment → Lab → Paper → Live`

---

## Pre-Promotion: Lab → Paper

### **Data Quality** ✅
- [ ] All data SLAs passing (m5_completeness >= 99%)
- [ ] No NaNs in OHLC columns
- [ ] No duplicate timestamps
- [ ] Session boundaries correct
- [ ] Timezone is UTC

### **Backtest Metrics** ✅
- [ ] Minimum 10 trades executed
- [ ] Win rate >= 55%
- [ ] Sharpe ratio >= 0.8
- [ ] Max drawdown <= -500 EUR
- [ ] No look-ahead bias verified

### **Code Quality** ✅
- [ ] All tests passing
- [ ] No linter errors
- [ ] Code reviewed
- [ ] Documentation updated

### **Configuration** ✅
- [ ] Strategy config in `configs/strategies/`
- [ ] Risk config reviewed (`configs/risk.yml`)
- [ ] Position sizing validated
- [ ] Guards configured

### **Artifacts** ✅
- [ ] Backtest results in `artifacts/backtests/`
- [ ] Equity curve generated
- [ ] Metrics JSON present
- [ ] Manifest complete

---

## Pre-Promotion: Paper → Live

### **Paper Trading Results** ✅
- [ ] Minimum 5 trading days completed
- [ ] Results match backtest (within 10%)
- [ ] No kill switch triggers
- [ ] Order fill rate >= 90%
- [ ] Average latency < 500ms (p95)

### **Technical Verification** ✅
- [ ] Idempotency keys working
- [ ] OCO orders functioning correctly
- [ ] No duplicate orders
- [ ] Guards triggering correctly
- [ ] Logs structured and parseable

### **Operational Readiness** ✅
- [ ] Monitoring dashboards configured
- [ ] Alerts set up (P0/P1 incidents)
- [ ] Runbook tested
- [ ] Team trained on incident response
- [ ] Broker confirmed (IBKR account verified)

### **Risk Management** ✅
- [ ] Position sizing validated
- [ ] Max exposure limits configured
- [ ] Kill switch tested
- [ ] Daily loss limit set
- [ ] Drawdown limit set

### **Disaster Recovery** ✅
- [ ] Backup strategy verified
- [ ] Rollback procedure tested
- [ ] Config backups in place
- [ ] Git tag created (e.g., `v1.5-paper-stable`)

---

## Promotion Commands

### Lab → Paper
```bash
# 1. Verify all checks pass
make promote:check CONFIG=configs/strategies/insidebar_v2.yml

# 2. Review promotion report
cat artifacts/promotion/report.json

# 3. Manual approval
read -p "Promote to Paper? (yes/no): " APPROVE

# 4. Execute promotion
if [ "$APPROVE" = "yes" ]; then
    make promote:paper CONFIG=configs/strategies/insidebar_v2.yml
fi

# 5. Verify Paper deployment
TR_MODE=paper make health-check
```

### Paper → Live
```bash
# 1. Create stable tag
git tag -a v1.5-paper-stable -m "Stable paper trading before live promotion"
git push --tags

# 2. Comprehensive checks
make promote:check-live CONFIG=configs/strategies/insidebar_v2.yml

# 3. Team review (REQUIRED)
# - Schedule review meeting
# - Share promotion report
# - Get approval from 2+ team members

# 4. Execute promotion (manual only)
TR_MODE=live make deploy

# 5. Monitor closely for first 24 hours
```

---

## Post-Promotion Monitoring

### First 24 Hours (Paper)
- [ ] Check logs every hour
- [ ] Verify orders are being sent
- [ ] Monitor fill rates
- [ ] Check position sizes
- [ ] Verify risk guards

### First 24 Hours (Live)
- [ ] Check logs every 15 minutes
- [ ] Verify actual positions match expected
- [ ] Monitor P&L in real-time
- [ ] Verify kill switch is armed
- [ ] Have rollback plan ready

### First Week
- [ ] Daily metrics review
- [ ] Compare actual vs backtest performance
- [ ] Review guard triggers
- [ ] Check for anomalies

---

## Rollback Triggers

**Immediate Rollback if:**
- Kill switch triggers in first 24 hours
- Loss exceeds 2x expected daily loss
- Duplicate orders detected
- Data SLA violations

**Planned Rollback if:**
- Performance significantly worse than backtest (> 20% deviation)
- Multiple guard triggers per day
- High order rejection rate (> 20%)

---

## Approval Record

### Lab → Paper Promotion
- **Date:** _______________
- **Strategy:** _______________
- **Approved by:** _______________
- **Promotion ID:** _______________

### Paper → Live Promotion
- **Date:** _______________
- **Strategy:** _______________
- **Paper Results:** _______________
- **Approved by (Primary):** _______________
- **Approved by (Secondary):** _______________
- **Promotion ID:** _______________

---

**Last Updated:** 2025-11-27
**Template Version:** 1.0
**Owner:** Trading Team
