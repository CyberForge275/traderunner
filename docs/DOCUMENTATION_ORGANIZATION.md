# Strategy Documentation Organization

## Strategy-Specific Documentation Moved

### InsideBar Strategy (`src/strategies/inside_bar/docs/`)
- ✅ `README.md` - Strategy overview and documentation
- ✅ `inside_bar_strategy.pdf` - Original strategy document
- ✅ `INSIDE_BAR_LIVE_TRADING.md` - Live trading integration guide (19KB)
- ✅ `UNIFIED_STRATEGY_PLAN.md` - Unified strategy implementation plan
- ✅ `UNIFIED_STRATEGY_SESSION_REPORT.md` - Session report

### Rudometkin MOC Strategy (`src/strategies/rudometkin_moc/docs/`)
- ✅ `README.md` - Strategy overview (placeholder)
- ✅ `rudometkin_moc_strategy.md` - Strategy description  
- ✅ `rudometkin_moc_long_short_translation.md` - Translation document
- ✅ `rudometkin_moc_long_short.rts.txt` - RTS file
- ✅ `code_review_rudometkin.md` - Code review
- ✅ `rk_strategy_10_day_report.md` - Performance report

### MA Crossover Strategy (`src/strategies/ma_crossover/docs/`)
- ✅ `README.md` - Strategy overview

## General Documentation (Remaining in `docs/`)

These files are NOT strategy-specific and remain in the main docs folder:

### System Architecture
- `Trading Software Factory (v2).pdf`
- `software_factory_trading_pipeline.pdf`
- `ENGINEERING_MANIFEST.md` / `.pdf`
- `V2_README.md`

### Deployment & Operations
- `DEPLOYMENT_QUICK_START.md`
- `MANUAL_DEPLOYMENT_STEPS.md`
- `TESTING_AND_DEPLOYMENT.md`
- `PRE_PAPERTRADE_SETUP.md`
- `PRE_PAPERTRADE_LAB_GUIDE.md`
- `PRE_PAPERTRADE_LAB_COMPLIANCE.md`
- `PAPER_TRADING_QUICKSTART.md`
- `PAPER_TRADING_CHECKLIST.md`
- `IB_GATEWAY_HEADLESS.md`

### System Integration
- `AUTO_SIGNAL_GENERATION.md`
- `FIX_EODHD_CONNECTION.md`
- `MARKET_HOURS_AUTOMATION.md`
- `REDIS_INTEGRATION_GUIDE.md`

### Testing & Lab
- `TIME_MACHINE_TESTING.md`
- `TEST_DATA.md`
- `DRY_RUN_RESULTS.md`

### Process & Lifecycle
- `STRATEGY_LIFECYCLE.md`
- `BACKTESTING_HANDOVER.md`
- `Dashboard_Analysis.md`
- `Implementation_plan.md`

### Historical/Archive
- `HANDOVER_DOCUMENTATION.md` (old)
- `reevaluation_report.md` (old)
- `configuration-pane-analysis.md` (old)
- `dr_plan.md` (old)

### Runbooks
- `runbooks/incident_response.md`
- `runbooks/promotion_checklist.md`

### Reference Material  
- `QUICK_REFERENCE.md`
- `Screenshot_TWS_*.png` (IB TWS screenshots)
- `ext_flow.jpg`, `screen1.png`, `backtest_dashboard_stream.png`

---

## Guidelines

For strategy-specific documentation, see: `src/strategies/docs/GUIDELINES.md`

All new strategies should have their documentation in `src/strategies/<strategy_name>/docs/`
