# v2 Architecture - README

> **📜 HISTORICAL/REFERENCE DOCUMENT**
> **Created**: November 2025
> **Status**: v2 architecture planning - partially implemented
> **Branch**: `feature/v2-architecture`

## Overview

This branch (`feature/v2-architecture`) contains the implementation of the v2 trading system architecture as defined in `docs/Trading Software Factory (v2).pdf`.

**Status:** 🚧 In Development

**Key Improvements over v1:**
- ✅ Explicit contracts for data, signals, and orders
- ✅ Deterministic idempotency for safe retries
- ✅ Data SLA enforcement
- ✅ Centralized risk management with guards
- ✅ Policy-driven automated promotion
- ✅ Comprehensive disaster recovery plan

---

## What's New in v2

### 1. Contracts (`src/axiom_bt/contracts/`)
Pydantic-based schemas for:
- **Data Contracts:** OHLCV validation with timezone, monotonicity, NaN checks
- **Signal Schema:** Canonical signal format with versioning
- **Order Schema:** Deterministic idempotency keys for retry safety

### 2. Validators (`src/axiom_bt/validators/`)
Data quality enforcement:
- M5 completeness >= 99%
- No NaNs in OHLC
- No duplicate timestamps
- Lateness monitoring

### 3. Risk Management (`src/axiom_bt/risk/`)
- **Position Sizing:** Fixed, % equity, risk-based modes
- **Guards:** Max exposure, daily loss, drawdown, per-symbol limits
- **Kill Switch:** Automated trading halt on breach

### 4. Policies (`configs/policies/`)
- **Promotion Policy:** Automated Lab→Paper→Live promotion based on thresholds
- **Risk Config:** Centralized risk parameters

### 5. Runbooks (`docs/runbooks/`)
- **Incident Response:** Step-by-step procedures for P0-P3 incidents
- **Promotion Checklist:** Pre-flight checks for stage promotions
- **DR Plan:** Disaster recovery with RTO/RPO targets

---

## Directory Structure (v2 Extensions)

```
traderunner/
├── src/axiom_bt/
│   ├── contracts/          # NEW: Data, signal, order schemas
│   ├── validators/         # NEW: SLA enforcement
│   └── risk/              # NEW: Sizing + guards
├── configs/
│   ├── policies/          # NEW: Promotion policies
│   └── risk.yml           # NEW: Risk configuration
├── docs/
│   ├── runbooks/          # NEW: Operational procedures
│   └── dr_plan.md         # NEW: Disaster recovery
└── artifacts/
    └── quality/           # NEW: SLA results
```

---

## Backward Compatibility

**v2 is designed to coexist with v1:**

- Old code paths remain unchanged
- New features opt-in via environment variables:
  ```bash
  export ENABLE_CONTRACTS=true
  export ENABLE_SLA_CHECKS=true
  export ENABLE_RISK_GUARDS=true
  ```

- Gradual migration path:
  1. Add contracts (validation optional)
  2. Integrate validators (warnings only)
  3. Enable guards (paper trading first)
  4. Enforce SLAs (block promotion)

---

## Usage Examples

### Contract Validation
```python
from axiom_bt.contracts.data_contracts import DailyFrameSpec

# Validate DataFrame
is_valid, violations = DailyFrameSpec.validate(df)
if not is_valid:
    print(f"Validation failed: {violations}")
```

### Position Sizing
```python
from axiom_bt.risk import PositionSizer, SizingMode, SizingConfig
from decimal import Decimal

# Risk-based sizing
config = SizingConfig(
    mode=SizingMode.RISK_BASED,
    equity=Decimal('10000'),
    risk_pct=1.0,
    max_pos_pct=20.0
)

sizer = PositionSizer(config)
qty = sizer.calculate(
    entry_price=Decimal('100'),
    stop_price=Decimal('98')
)
print(f"Position size: {qty} shares")
```

### Risk Guards
```python
from axiom_bt.risk.guards import create_default_guards

# Create guard registry
guards = create_default_guards(
    max_daily_loss=Decimal('1000'),
    max_drawdown=Decimal('1500')
)

# Check order
rejection = guards.check_all(order, portfolio)
if rejection:
    print(f"Order rejected: {rejection.reason}")
else:
    broker.send_order(order)
```

### Data SLA Checks
```python
from axiom_bt.validators import DataQualitySLA

# Check all SLAs
results = DataQualitySLA.check_all(df)

for sla_name, result in results.items():
    if result.passed:
        print(f"✅ {sla_name}: {result.message}")
    else:
        print(f"❌ {sla_name}: {result.message}")
```

---

## Testing

### Unit Tests (TODO)
```bash
# Test contracts
pytest tests/test_contracts.py

# Test validators
pytest tests/test_validators.py

# Test risk guards
pytest tests/test_guards.py

# Test position sizing
pytest tests/test_sizing.py
```

### Integration Tests (TODO)
```bash
# End-to-end pipeline test
pytest tests/integration/test_signal_to_order_pipeline.py
```

---

## Migration Roadmap

### ✅ Phase 1: Foundation (Completed)
- [x] Create v2 directory structure
- [x] Implement contracts
- [x] Implement validators
- [x] Implement risk guards
- [x] Write runbooks

### ⏳ Phase 2: Integration (In Progress)
- [ ] Add contract validation to cli_data.py
- [ ] Integrate SLA checks into data pipeline
- [ ] Wire risk guards into order export
- [ ] Add idempotency to order generation

### 📋 Phase 3: Testing
- [ ] Write unit tests for contracts
- [ ] Write unit tests for validators
- [ ] Write unit tests for risk guards
- [ ] Property-based tests for sizing invariants
- [ ] Integration tests for full pipeline

### 🚀 Phase 4: Deployment
- [ ] Enable contracts in Lab
- [ ] Enable SLA checks in Lab
- [ ] Enable risk guards in Paper
- [ ] Implement promotion CLI
- [ ] Deploy to Paper trading

---

## Rollback Safety

**To revert to v1 (stable):**
```bash
git checkout main
# or
git checkout v1.0-stable
```

**All v1 functionality remains unchanged.** The `main` branch contains the stable v1 implementation with tag `v1.0-stable`.

---

## Dependencies

**New in v2:**
- `pydantic` - Contract validation
- `pandera` (optional) - DataFrame schema validation

**Install:**
```bash
pip install pydantic
# Optional:
pip install pandera
```

---

## Documentation

- **Architecture:** `docs/Trading Software Factory (v2).pdf`
- **Incident Response:** `docs/runbooks/incident_response.md`
- **Promotion Checklist:** `docs/runbooks/promotion_checklist.md`
- **DR Plan:** `docs/dr_plan.md`

---

## Contributing to v2

1. Create feature branch from `feature/v2-architecture`:
   ```bash
   git checkout feature/v2-architecture
   git checkout -b feature/v2-contracts-enhancement
   ```

2. Make changes, test locally

3. Create pull request to merge back into `feature/v2-architecture`

4. Once v2 is stable, we'll merge `feature/v2-architecture` → `main`

---

## Questions?

- Review `docs/Trading Software Factory (v2).pdf` for architecture details
- Check `docs/runbooks/` for operational procedures
- Open an issue in GitHub for discussions

---

**Branch:** `feature/v2-architecture`
**Created:** 2025-11-27
**Status:** Development
**Target Merge:** TBD (after comprehensive testing)
