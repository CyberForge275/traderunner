# P3-C1 Handoff: InsideBar → TradeTemplates Adapter

**Goal**: Replace minimal test templates in runner compound path with real InsideBar strategy signals

**Status**: Ready to implement  
**Branch**: main  
**Prerequisites**: Phase 2 complete (75/75 tests passing)

---

## Non-Negotiables

- ✅ Branch: `main` only
- ✅ 1 deliverable per commit
- ✅ Max 1-3 files per commit
- ✅ Default path unchanged (`compound_sizing=false` → legacy)
- ✅ No artifacts/debug files in commits
- ✅ Proof command after each commit

---

## Discovery Checklist

Before implementation, answer these questions:

1. **Where do InsideBar entries/exits originate?**
   ```bash
   rg -n "generate_signals|create_orders|entry|exit" src/strategies/inside_bar/
   rg -n "class InsideBar" src/strategies/
   ```

2. **What structure do signals/trades have?**
   - DataFrame columns?
   - Dict/object structure?
   - Required fields: symbol, entry_ts, entry_price, exit_ts, exit_price, side, reason?

3. **Where are signals currently consumed?**
   ```bash
   rg -n "signals|orders|trades" src/axiom_bt/full_backtest_runner.py
   ```

4. **What does TradeTemplate need?**
   - Required: `template_id, symbol, side, entry_ts, entry_price, entry_reason`
   - Optional: `exit_ts, exit_price, exit_reason`
   - NO qty field (calculated at execution time)

5. **Current runner compound path (L240-295)?**
   - Creates hardcoded test templates
   - Needs replacement with real adapter call

---

## Implementation Plan (Mini-Steps)

### P3-C1a: Adapter Module + Unit Tests
**Files**: 
- `src/axiom_bt/strategy_adapters/inside_bar_to_templates.py` (new)
- `tests/test_p3_c1_inside_bar_adapter.py` (new, 6-8 tests)

**Scope**:
- `inside_bar_to_trade_templates(signals) -> list[TradeTemplate]`
- Deterministic `template_id` generation (hash of symbol+entry_ts+side)
- Map signal fields → TradeTemplate fields
- Validate: raise if prices missing
- No qty field

**Tests**:
- Deterministic template_id
- Correct field mapping (entry/exit ts, prices, side)
- Shuffle-invariant output
- Rejects invalid input (missing prices)
- Empty signals → empty templates (valid)

**Proof**:
```bash
pytest -xvs tests/test_p3_c1_inside_bar_adapter.py
pytest -q tests/test_compound_*.py tests/test_f1*.py tests/test_f2*.py tests/test_p3*.py
```

**Commit**: `feat(p3-c1a): add insidebar->template adapter with unit tests`

---

### P3-C1b: Runner Uses Adapter
**Files**:
- `src/axiom_bt/full_backtest_runner.py` (modify compound path L240-295)

**Scope**:
- Remove hardcoded test template creation
- Call adapter with real signals/data
- Handle empty template list (0 events → SUCCESS with 0 processed)
- Pipeline unchanged: `templates → events → ordering → engine`

**Changes**:
```python
# OLD (L253-264):
templates = [
    TradeTemplate(
        template_id="test_template_1",
        ...  # hardcoded test data
    ),
]

# NEW:
from axiom_bt.strategy_adapters.inside_bar_to_templates import inside_bar_to_trade_templates
templates = inside_bar_to_trade_templates(signals_or_data)
```

**Proof**:
```bash
pytest -q tests/test_compound_*.py tests/test_f1*.py tests/test_f2*.py tests/test_p3*.py
# All existing tests still pass
```

**Commit**: `feat(p3-c1b): runner uses real insidebar signals via adapter`

---

### P3-C1c: Integration Test
**Files**:
- `tests/test_p3_c1_inside_bar_adapter.py` (add integration test)

**Scope**:
- Spy/monkeypatch: verify runner calls adapter (not test template builder)
- Verify result contains `num_templates > 0` when signals present
- Smoke test: compound path end-to-end with real adapter

**Proof**:
```bash
pytest -xvs tests/test_p3_c1_inside_bar_adapter.py::test_runner_integration
pytest -q tests/test_compound_*.py tests/test_f1*.py tests/test_f2*.py tests/test_p3*.py
```

**Commit**: `test(p3-c1c): add integration test for adapter in runner`

---

## Proof Commands

**After each step**:
```bash
pytest -q tests/test_compound_*.py tests/test_f1*.py tests/test_f2*.py tests/test_p3*.py
git status
```

**Expected**: All tests pass, git status clean

---

## Risks & Mitigation

1. **Signal structure unknown**
   - Mitigation: Discovery first, adapt to existing structure
   - Don't rewrite strategy, just map existing output

2. **Heavy imports (normalize_session_filter trap)**
   - Mitigation: Avoid importing runner in tests
   - Use minimal fixtures, no actual backtests in unit tests

3. **Determinism of template_id**
   - Mitigation: Use hash of (symbol, entry_ts, side) for stable IDs
   - Test with shuffle-invariance assertions

4. **Empty signals edge case**
   - Mitigation: Adapter returns empty list → valid
   - EventEngine handles 0 events gracefully (already tested)

---

## Success Criteria

✅ No hardcoded test templates in runner  
✅ Adapter produces valid TradeTemplates from real signals  
✅ Deterministic template_id generation  
✅ All existing tests pass (regression clean)  
✅ New P3-C1 tests pass (6-8 tests minimum)  
✅ Default path unchanged (`compound_sizing=false`)

---

**Next Session**: Start with discovery, then implement P3-C1a → P3-C1b → P3-C1c
