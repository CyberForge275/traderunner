# EODHD Consolidation Backlog

**Created**: 2025-12-10
**Priority**: Medium-Term Infrastructure Improvements

---

## ✅ Completed

### Phase 0: Environment Variable Standardization
**Status**: ✅ COMPLETE
**Risk**: VERY LOW
**Duration**: 15 minutes

**Changes**:
- [x] Pre-PaperTrade adapter supports both variables
- [x] marketdata-stream/mode_manager.py updated
- [x] marketdata-stream/strategy_runner.py updated
- [x] Tests updated

**Pattern**:
```python
api_key = os.getenv("EODHD_API_KEY") or os.getenv("EODHD_API_TOKEN")
```

---

## 🎯 Backlog (Prioritized)

### Phase 1: ParquetRepository Abstraction
**Priority**: HIGH
**Risk**: LOW
**Estimated Duration**: 2-3 days

**Objective**: Create centralized parquet file access layer

**Tasks**:
- [ ] Create `traderunner/src/data/parquet_repository.py`
- [ ] Implement read/write/list methods
- [ ] Add validation layer
- [ ] Integrate with DataManager for auto-download
- [ ] Write unit tests
- [ ] Update Pre-PaperTrade to use ParquetRepository
- [ ] Document API

**Success Criteria**:
- ✅ ParquetRepository class functional
- ✅ All reads go through validation
- ✅ Auto-download works transparently
- ✅ Pre-PaperTrade uses it successfully
- ✅ Unit tests pass

**Benefits**:
- Single point of control for parquet access
- Consistent validation across codebase
- Foundation for future migrations

---

### Phase 2: Backtesting Migration to DataManager
**Priority**: MEDIUM
**Risk**: MEDIUM
**Estimated Duration**: 3-5 days

**Objective**: Migrate backtesting engine to use DataManager instead of direct EODHD API calls

**Tasks**:
- [ ] Review `src/axiom_bt/data/eodhd_fetch.py` usage
- [ ] Create DataManager wrapper for backtesting
- [ ] Migrate `src/axiom_bt/cli_data.py` to use DataManager
- [ ] Update `src/axiom_bt/intraday.py` to use DataManager
- [ ] Test with single strategy (e.g., InsideBar)
- [ ] Test with multiple strategies
- [ ] Compare results (ensure identical)
- [ ] Deprecate `eodhd_fetch.py` (mark with warning)
- [ ] Update documentation

**Success Criteria**:
- ✅ Backtests produce identical results
- ✅ Data fetching uses DataManager
- ✅ No duplicate downloads (caching works)
- ✅ Performance unchanged or improved
- ✅ All tests pass

**Rollback Plan**:
- Keep old code for 2 sprints
- Feature flag to switch between implementations
- Easy revert if issues

---

### Phase 3: WebSocket Client Consolidation
**Priority**: LOW
**Risk**: HIGH
**Estimated Duration**: 1-2 weeks

**Objective**: Consolidate 3 WebSocket implementations into single canonical version

**Investigation First**:
- [ ] Determine which clients are actively used
- [ ] Map dependencies
- [ ] Identify differences in functionality
- [ ] Create migration plan

**Tasks**:
- [ ] Choose canonical implementation (`providers/eodhd.py` recommended)
- [ ] Document differences between clients
- [ ] Create adapter layer if needed
- [ ] Migrate `eodhd_client.py` usage to canonical
- [ ] Migrate `eodhd_client_simple.py` usage to canonical
- [ ] Review `eodhd_bridge.py` - consolidate or remove
- [ ] Update all imports
- [ ] Test thoroughly in staging
- [ ] Deploy with rollback plan
- [ ] Deprecate old clients

**Success Criteria**:
- ✅ Single WebSocket client in use
- ✅ All subscriptions work
- ✅ No data loss
- ✅ Performance maintained
- ✅ Live trading unaffected

**Rollback Plan**:
- Keep old clients for 1 month
- Monitor for issues
- Quick rollback capability

---

### Phase 4: Full Parquet Access Migration
**Priority**: LOW
**Risk**: MEDIUM-HIGH
**Estimated Duration**: 2-3 weeks

**Objective**: Migrate all 60+ direct parquet access points to use ParquetRepository

**Tasks**:
- [ ] Audit all 60+ files accessing parquet
- [ ] Categorize by usage pattern
- [ ] Create migration plan (priority order)
- [ ] Migrate high-priority files first
  - [ ] Dashboard repositories
  - [ ] Signal generation
  - [ ] Backtesting
- [ ] Migrate medium-priority files
  - [ ] Utilities
  - [ ] Scripts
- [ ] Migrate low-priority files
  - [ ] Tests
  - [ ] Examples
- [ ] Update all imports
- [ ] Remove direct `pd.read_parquet()` calls
- [ ] Verify all functionality unchanged
- [ ] Update documentation

**Success Criteria**:
- ✅ All files use ParquetRepository
- ✅ No direct parquet access
- ✅ All tests pass
- ✅ Performance unchanged
- ✅ Code coverage maintained

**Migration Pattern**:
```python
# OLD:
df = pd.read_parquet(f"artifacts/data_m5/{symbol}.parquet")

# NEW:
from data.parquet_repository import get_parquet_repo
repo = get_parquet_repo()
df = repo.read(symbol=symbol, timeframe="M5")
```

---

### Phase 5: Shared Library Extraction (Future)
**Priority**: VERY LOW
**Risk**: LOW
**Estimated Duration**: 1 week

**Objective**: Extract common data code into shared library

**Tasks**:
- [ ] Create `droid-common` package
- [ ] Extract DataManager
- [ ] Extract ParquetRepository
- [ ] Extract EODHD client
- [ ] Extract WebSocket provider
- [ ] Publish to private PyPI or use git submodule
- [ ] Update traderunner to use droid-common
- [ ] Update marketdata-stream to use droid-common
- [ ] Update automatictrader-api to use droid-common

**Benefits**:
- True single source of truth
- Shared across all projects
- Versioned releases
- Easier testing

---

## 📊 Risk Assessment Summary

| Phase | Priority | Risk | Duration | Dependencies |
|---|---|---|---|---|
| 0. Env Vars | HIGH | VERY LOW | 15min | None |
| 1. ParquetRepo | HIGH | LOW | 2-3 days | Phase 0 |
| 2. Backtesting | MEDIUM | MEDIUM | 3-5 days | Phase 1 |
| 3. WebSocket | LOW | HIGH | 1-2 weeks | None |
| 4. Full Migration | LOW | MEDIUM-HIGH | 2-3 weeks | Phase 1, 2 |
| 5. Shared Lib | VERY LOW | LOW | 1 week | Phase 1-4 |

---

## 🎯 Recommended Timeline

**This Sprint** (Week 1):
- ✅ Phase 0 complete
- 🎯 Phase 1: ParquetRepository

**Next Sprint** (Week 2-3):
- Phase 2: Backtesting migration

**Future** (Month 2):
- Phase 3: WebSocket consolidation

**Future** (Month 3+):
- Phase 4: Full parquet migration
- Phase 5: Shared library

---

## 📝 Notes

- **Phase 0** is complete and safe
- **Phase 1** is low-risk and provides foundation
- **Phase 2** should be tested thoroughly
- **Phase 3** requires careful planning (live trading affects)
- **Phase 4** is gradual, can spread over time
- **Phase 5** is optional, nice-to-have

---

**Status**: Actively managing
**Owner**: Engineering team
**Last Updated**: 2025-12-10
