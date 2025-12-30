# BACKTESTING CONTRACT TEST PLAN

**Status:** Test Strategy & Enforcement Plan
**Companion Doc:** [BACKTESTING_INTERFACE_CONTRACT.md](./BACKTESTING_INTERFACE_CONTRACT.md)
**Purpose:** Define comprehensive test coverage to enforce contract compliance forever.

---

## Overview

This document describes the test architecture required to enforce the backtesting contract invariants across all modes (INTRADAY, DAYTRADING, HYBRID). Tests are organized in layers:

1. **Unit-level contract tests** - Fast, synthetic data, validate individual invariants
2. **Integration contract tests** - Fixture-based, end-to-end validation with cheap artifacts
3. **Architecture separation tests** - Enforce layering and dependency boundaries
4. **CI gate strategy** - Automated enforcement in continuous integration
5. **Evidence regression checks** - Statistical analysis for lookahead detection

---

## A. Unit-Level Contract Tests (Synthetic Data)

### A.1 Test Data Generator

Create a deterministic synthetic data generator for testing:

```python
def generate_synthetic_rth_bars(
    symbol: str = "TEST",
    market_tz: str = "America/New_York",
    num_days: int = 2,
    base_tf: str = "1min"
) -> pd.DataFrame:
    """
    Generate RTH-only minute bars with:
    - Known patterns (e.g., inside bar on day 1)
    - Known entry/TP/SL touch points
    - Consistent timezone (market_tz)
    - No pre/post market data

    Returns DataFrame with columns: ts, open, high, low, close, volume
    """
```

**Key characteristics:**
- RTH hours only: 09:30-16:00 ET
- Day 1: Setup pattern (e.g., mother bar)
- Day 2: Signal bar (inside bar) + execution bars with known touches
- Deterministic OHLCV values for reproducible assertions

### A.2 Signal Grid Alignment Tests

**Test:** `test_signal_grid_alignment_m5()`

**Objective:** Verify signal timestamps align to M5 grid boundaries

**Setup:**
- Generate M1 RTH bars
- Resample to M5 with `label=left`, `closed=left`
- Generate synthetic signal at specific M5 bar

**Assertions:**
```python
assert signal_ts.minute % 5 == 0  # Must be on 5-minute boundary
assert signal_ts in signal_bars.index  # Must exist in signal bar index
assert signal_ts.second == 0  # No sub-minute precision
```

**Invariants tested:** `BAR-2`

---

**Test:** `test_signal_grid_alignment_daily()`

**Objective:** Verify daily signals align to market close (16:00 ET)

**Setup:**
- Generate M1 bars for 2 days
- Resample to D1
- Generate daily signal at prior day close

**Assertions:**
```python
assert signal_ts.time() == time(16, 0)  # Must be at market close
assert signal_ts.date() == expected_signal_date
```

**Invariants tested:** `BAR-2`, `HYB-2`

---

### A.3 RTH Filter Tests

**Test:** `test_rth_filter_excludes_pre_post()`

**Objective:** Verify RTH filter excludes pre/aftermarket bars

**Setup:**
- Generate bars from 04:00-20:00 ET (includes pre/post)
- Apply RTH filter with `rth_start=09:30`, `rth_end=16:00`

**Assertions:**
```python
filtered = apply_rth_filter(all_bars, market_tz="America/New_York")

assert filtered.index.min().time() >= time(9, 30)  # No pre-market
assert filtered.index.max().time() < time(16, 0)   # No after-market
assert len(filtered) == expected_rth_bar_count
```

**Invariants tested:** `RTH-1`, `RTH-2`

---

**Test:** `test_rth_filter_timezone_conversion_correctness()`

**Objective:** Verify RTH filter operates in market_tz before UTC conversion

**Setup:**
- Generate bars in UTC with DST transition
- Convert to ET, apply RTH filter
- Verify DST-aware filtering

**Assertions:**
```python
# During DST: 09:30 ET = 13:30 UTC
# Standard: 09:30 ET = 14:30 UTC
rth_bars = apply_rth_filter_market_tz(utc_bars, market_tz="America/New_York")

assert all(9.5 <= hour_in_et(ts) < 16 for ts in rth_bars.index)
```

**Invariants tested:** `TZ-1`, `RTH-1`, `DATA-2`

---

### A.4 Earliest-Touch Entry Tests

**Test:** `test_earliest_touch_entry_long()`

**Objective:** Verify LONG entry executes on first bar where `high >= entry_level`

**Setup:**
- M1 bars with known OHLCV:
  - Bar 1: high=27.50 (below entry 28.50)
  - Bar 2: high=28.75 (touches entry)
  - Bar 3: high=29.00 (also above entry)
- LONG order with `entry_level=28.50`

**Assertions:**
```python
filled_entry = execute_entry_order(order, exec_bars_m1)

assert filled_entry.fill_ts == bar_2_ts  # Earliest touch
assert filled_entry.fill_price >= 28.50  # At or above entry
assert filled_entry.fill_price <= bar_2_high  # Within bar range
```

**Invariants tested:** `EXEC-1`, `EXEC-2`

---

**Test:** `test_earliest_touch_entry_short()`

**Objective:** Verify SHORT entry executes on first bar where `low <= entry_level`

**Setup:**
- M1 bars:
  - Bar 1: low=29.50 (above entry 28.50)
  - Bar 2: low=28.30 (touches entry)
  - Bar 3: low=27.80

**Assertions:**
```python
filled_entry = execute_entry_order(short_order, exec_bars_m1)

assert filled_entry.fill_ts == bar_2_ts
assert filled_entry.fill_price <= 28.50
assert filled_entry.fill_price >= bar_2_low
```

**Invariants tested:** `EXEC-1`, `EXEC-2`

---

### A.5 Earliest-Touch Exit Tests

**Test:** `test_earliest_touch_exit_tp_long()`

**Objective:** Verify LONG TP executes on first bar where `high >= tp_level`

**Setup:**
- Active LONG position from entry_ts
- M1 bars after entry with known touches
- TP level = 30.00

**Assertions:**
```python
exit_fill = monitor_exit_conditions(long_position, exec_bars_m1)

assert exit_fill.exit_reason == "TP"
assert exit_fill.fill_ts == first_bar_ts_where_high_gte_30
assert exit_fill.fill_price <= bar_high
assert exit_fill.fill_price >= tp_level
```

**Invariants tested:** `EXEC-1`, `EXEC-2`

---

**Test:** `test_earliest_touch_exit_sl_long()`

**Objective:** Verify LONG SL executes on first bar where `low <= sl_level`

**Setup:**
- Active LONG position
- SL level = 27.00
- Known bar where low touches SL

**Assertions:**
```python
exit_fill = monitor_exit_conditions(long_position, exec_bars_m1)

assert exit_fill.exit_reason == "SL"
assert exit_fill.fill_price >= sl_level - max_slippage
assert exit_fill.fill_price <= sl_level
```

**Invariants tested:** `EXEC-1`, `EXEC-2`

---

**Test:** `test_sl_executes_before_tp_when_both_touched_same_bar()`

**Objective:** Verify SL takes precedence when both SL and TP touched in same bar (conservative assumption)

**Setup:**
- LONG position with SL=27, TP=30
- Single bar with low=26.50, high=30.50 (touches both)

**Assertions:**
```python
exit_fill = monitor_exit_conditions(long_position, exec_bars_m1)

assert exit_fill.exit_reason == "SL"  # Conservative: SL wins
```

**Invariants tested:** `EXEC-1`

---

### A.6 Fill Price Plausibility Tests

**Test:** `test_fill_within_exec_bar_range()`

**Objective:** Verify all fills respect bar OHLC boundaries

**Setup:**
- Execute multiple orders on synthetic data
- Collect all fills (entry + exits)

**Assertions:**
```python
for fill in all_fills:
    exec_bar = exec_bars.loc[fill.bar_ts_exec]

    assert exec_bar.low <= fill.fill_price <= exec_bar.high
    # Or if slippage model allows push beyond:
    assert within_slippage_tolerance(fill.fill_price, exec_bar, slippage_model)
```

**Invariants tested:** `EXEC-2`

**Evidence codes:** Should add `FILL_WITHIN_BAR_OK` or `FILL_OUTSIDE_BAR`

---

### A.7 Deterministic ID Tests

**Test:** `test_deterministic_ids_stable_across_runs()`

**Objective:** Verify IDs are reproducible given identical inputs

**Setup:**
- Run backtest twice with identical config and data
- Collect orders, fills, trades from both runs

**Assertions:**
```python
run1_orders = load_orders("run1/orders.csv")
run2_orders = load_orders("run2/orders.csv")

assert run1_orders["order_id"].tolist() == run2_orders["order_id"].tolist()
assert run1_orders["signal_id"].tolist() == run2_orders["signal_id"].tolist()

# Same for fills, trades
```

**Invariants tested:** `ID-1`

---

**Test:** `test_deterministic_id_components()`

**Objective:** Verify IDs include all required components per contract

**Setup:**
- Generate signal, order, trade, fill
- Inspect ID generation logic

**Assertions:**
```python
signal_id = generate_signal_id(run_id, symbol, signal_ts, side, key_levels)
order_id = generate_order_id(signal_id, validity_window, entry_level)
trade_id = generate_trade_id(order_id, entry_fill_ts)
fill_id = generate_fill_id(trade_id, fill_type, fill_ts)

# Verify hash stability
assert signal_id == hash_deterministic(run_id, symbol, signal_ts, side, key_levels)
```

**Invariants tested:** `ID-1`

---

### A.8 Lineage Integrity Tests

**Test:** `test_lineage_orders_fills_trades_1to1()`

**Objective:** Verify every trade maps to exactly one entry and one exit fill

**Setup:**
- Run backtest with known outcomes
- Load orders, fills, trades

**Assertions:**
```python
for trade in trades:
    entry_fills = filled_orders[
        (filled_orders.trade_id == trade.trade_id) &
        (filled_orders.fill_type == "ENTRY")
    ]
    exit_fills = filled_orders[
        (filled_orders.trade_id == trade.trade_id) &
        (filled_orders.fill_type == "EXIT")
    ]

    assert len(entry_fills) == 1, f"Trade {trade.trade_id} has {len(entry_fills)} entries"
    assert len(exit_fills) == 1, f"Trade {trade.trade_id} has {len(exit_fills)} exits"
```

**Invariants tested:** `LIN-1`, `LIN-2`

---

**Test:** `test_orphaned_fills_detection()`

**Objective:** Verify no fills exist without corresponding orders/trades

**Setup:**
- Load all artifacts
- Cross-reference IDs

**Assertions:**
```python
all_order_ids = set(orders.order_id)
all_trade_ids = set(trades.trade_id)

for fill in filled_orders.itertuples():
    assert fill.order_id in all_order_ids, f"Orphaned fill: {fill.fill_id}"
    assert fill.trade_id in all_trade_ids, f"Fill missing trade: {fill.fill_id}"
```

**Invariants tested:** `LIN-2`

---

## B. Integration Contract Tests (Fixture-Based, Cheap)

### B.1 Fixture Run Setup

**Location:** `tests/fixtures/backtests/contract_fixture_run_001/`

**Contents:**
- `run_meta.json` - Small hybrid run config
- `orders.csv` - 5 orders (3 filled, 2 expired)
- `filled_orders.csv` - 6 fills (3 entry, 3 exit)
- `trades.csv` - 3 completed trades
- `bars/bars_signal_D1_rth.parquet` - 5 daily bars
- `bars/bars_exec_M1_rth.parquet` - ~1000 M1 bars (2 days RTH)
- `equity_curve.csv`
- `run_steps.jsonl`
- `run_manifest.json`

**Characteristics:**
- Deterministic, committed to repo
- Never fetches from EODHD (static fixture)
- Covers HYBRID mode edge cases
- Includes evidence codes: PASS, WARN (one degraded trade)

---

### B.2 Acceptance Criteria Tests

**Test:** `test_contract_acceptance_all_artifacts_present()`

**Objective:** Verify all required artifacts exist per contract §8

**Setup:**
- Load fixture run directory

**Assertions:**
```python
required_artifacts = [
    "run_meta.json",
    "orders.csv",
    "filled_orders.csv",
    "trades.csv",
    "equity_curve.csv",
    "bars/bars_signal_D1_rth.parquet",
    "bars/bars_exec_M1_rth.parquet",
    "run_manifest.json"
]

for artifact in required_artifacts:
    assert (fixture_dir / artifact).exists(), f"Missing: {artifact}"
```

**Invariants tested:** `ART-1`, `AUD-2`

---

**Test:** `test_contract_acceptance_rth_enforcement()`

**Objective:** Verify RTH-only enforcement in persisted bars

**Setup:**
- Load `bars_exec_M1_rth.parquet`
- Check bar timestamps

**Assertions:**
```python
exec_bars = pd.read_parquet(fixture_dir / "bars/bars_exec_M1_rth.parquet")

# Convert to market_tz from metadata
market_tz = load_meta()["market_tz"]
bars_et = exec_bars.tz_convert(market_tz)

for ts in bars_et.index:
    assert 9.5 <= ts.hour + ts.minute/60 < 16, f"Non-RTH bar: {ts}"
```

**Invariants tested:** `RTH-1`, `RTH-2`

---

**Test:** `test_contract_acceptance_signal_grid_alignment()`

**Objective:** Verify signal timestamps in orders align to signal_tf

**Setup:**
- Load orders.csv, run_meta.json
- Extract signal_tf (e.g., "D1")

**Assertions:**
```python
signal_tf = meta["signal_tf"]
orders = pd.read_csv(fixture_dir / "orders.csv", parse_dates=["created_from_ts"])

if signal_tf == "D1":
    for ts in orders.created_from_ts:
        # Daily signals should be at market close (16:00 ET)
        ts_et = ts.tz_convert(meta["market_tz"])
        assert ts_et.time() == time(16, 0)
```

**Invariants tested:** `BAR-2`, `INTRA-2`

---

**Test:** `test_contract_acceptance_earliest_touch_execution()`

**Objective:** Verify fills occur on earliest bar satisfying touch condition

**Setup:**
- Load filled_orders.csv, bars_exec_M1_rth.parquet
- For each entry fill, verify no earlier bar could have filled

**Assertions:**
```python
for fill in filled_orders[filled_orders.fill_type == "ENTRY"].itertuples():
    order = orders[orders.order_id == fill.order_id].iloc[0]

    # Get all bars between valid_from and fill_ts
    eligible_bars = exec_bars[order.valid_from_ts : fill.fill_ts]

    # Verify fill_ts is earliest bar where touch condition met
    if order.side == "LONG":
        earlier_touches = eligible_bars[eligible_bars.high >= order.entry_level]
    else:
        earlier_touches = eligible_bars[eligible_bars.low <= order.entry_level]

    assert earlier_touches.index[0] == fill.bar_ts_exec
```

**Invariants tested:** `EXEC-1`

---

**Test:** `test_contract_acceptance_fill_price_plausibility()`

**Objective:** Verify all fill prices are within bar OHLC

**Setup:**
- Load filled_orders.csv, bars_exec_M1_rth.parquet

**Assertions:**
```python
for fill in filled_orders.itertuples():
    exec_bar = exec_bars.loc[fill.bar_ts_exec]

    assert exec_bar.low <= fill.fill_price <= exec_bar.high, \
        f"Fill {fill.fill_id} price {fill.fill_price} outside bar [{exec_bar.low}, {exec_bar.high}]"
```

**Invariants tested:** `EXEC-2`

---

**Test:** `test_contract_acceptance_deterministic_ids()`

**Objective:** Verify IDs are deterministic (can be regenerated)

**Setup:**
- Load orders, recompute IDs from components

**Assertions:**
```python
for order in orders.itertuples():
    recomputed_id = generate_order_id_deterministic(
        order.signal_id,
        order.valid_from_ts,
        order.valid_to_ts,
        order.entry_level
    )

    assert order.order_id == recomputed_id
```

**Invariants tested:** `ID-1`

---

**Test:** `test_contract_acceptance_lineage_integrity()`

**Objective:** Verify 1:1 lineage mappings

**Assertions:**
```python
# Every trade has exactly 1 entry, 1 exit
for trade in trades.itertuples():
    entries = filled_orders[
        (filled_orders.trade_id == trade.trade_id) &
        (filled_orders.fill_type == "ENTRY")
    ]
    exits = filled_orders[
        (filled_orders.trade_id == trade.trade_id) &
        (filled_orders.fill_type == "EXIT")
    ]

    assert len(entries) == 1
    assert len(exits) == 1
```

**Invariants tested:** `LIN-1`, `LIN-2`

---

**Test:** `test_contract_acceptance_evidence_codes_complete()`

**Objective:** Verify all trades have evidence codes and status

**Setup:**
- Load trades.csv

**Assertions:**
```python
for trade in trades.itertuples():
    assert trade.evidence_status in ["PASS", "WARN", "FAIL"]
    assert isinstance(trade.evidence_codes, str)
    assert len(trade.evidence_codes) > 0

    # Verify codes are from canonical list
    for code in trade.evidence_codes.split(","):
        assert code.strip() in CANONICAL_EVIDENCE_CODES
```

**Invariants tested:** `EVID-1`

---

## C. Architecture Separation Tests

### C.1 Layer Boundary Tests

**Test:** `test_no_ui_imports_in_service_layer()`

**Objective:** Enforce separation: services must not import from `trading_dashboard.layouts` or `callbacks`

**Setup:**
- Static analysis of service modules

**Assertions:**
```python
service_modules = [
    "trading_dashboard/services/trade_detail_service.py",
    "trading_dashboard/services/backtest_details_service.py",
    "src/backtest/services/"
]

for module_path in service_modules:
    source = read_file(module_path)

    # Forbidden imports
    assert "from trading_dashboard.layouts" not in source
    assert "from trading_dashboard.callbacks" not in source
    assert "import dash" not in source or "# permitted" in source
```

**Invariants tested:** Engineering Manifest separation of concerns

---

**Test:** `test_no_business_logic_in_ui_callbacks()`

**Objective:** Callbacks should only orchestrate; business logic must be in services

**Setup:**
- Analyze callback files for disallowed patterns

**Assertions:**
```python
callback_files = glob("trading_dashboard/callbacks/*.py")

for callback_file in callback_files:
    source = read_file(callback_file)

    # Callbacks should delegate, not compute
    assert "def calculate_" not in source  # Computation should be in service
    assert "pd.DataFrame" in source implies "service." in source  # DataFrames from services
```

**Invariants tested:** Engineering Manifest UI/business logic separation

---

### C.2 SSOT Artifact Tests

**Test:** `test_artifacts_are_read_only_in_consumers()`

**Objective:** Dashboard/analysis tools must not mutate artifacts

**Setup:**
- Static analysis of repository and service modules

**Assertions:**
```python
consumer_modules = glob("trading_dashboard/repositories/*.py")

for module_path in consumer_modules:
    source = read_file(module_path)

    # Repositories should only read artifacts
    assert ".to_csv(" not in source  # No writing
    assert ".to_parquet(" not in source
    assert "with open(" in source implies "'r'" in source  # Read-only mode
```

**Invariants tested:** SSOT immutability

---

## D. CI Gate Proposal (Doc-Only)

### D.1 Contract Gate Job

**Objective:** Fast-fail CI job that runs only contract tests

**Configuration (GitHub Actions example):**
```yaml
name: Contract Gate

on: [push, pull_request]

jobs:
  contract-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt

      - name: Run Contract Unit Tests
        run: |
          pytest tests/contract/unit/ -v --tb=short

      - name: Run Contract Integration Tests
        run: |
          pytest tests/contract/integration/ -v --tb=short

      - name: Run Architecture Separation Tests
        run: |
          pytest tests/architecture/ -v --tb=short

      - name: Contract Compliance Report
        if: failure()
        run: |
          echo "❌ Contract violation detected. See test output above."
          exit 1
```

**Success criteria:**
- All contract tests PASS
- Run time < 5 minutes (enforced by timeout)
- No external dependencies (EODHD, live DB)

**Failure behavior:**
- Block merge if any contract test fails
- Require manual override with justification

---

### D.2 Test Organization

**Directory structure:**
```
tests/
├── contract/
│   ├── unit/
│   │   ├── test_signal_grid_alignment.py
│   │   ├── test_rth_filter.py
│   │   ├── test_earliest_touch.py
│   │   ├── test_fill_plausibility.py
│   │   ├── test_deterministic_ids.py
│   │   └── test_lineage_integrity.py
│   └── integration/
│       ├── test_contract_acceptance_criteria.py
│       └── fixtures/
│           └── backtests/
│               └── contract_fixture_run_001/
│                   ├── run_meta.json
│                   ├── orders.csv
│                   └── ...
├── architecture/
│   ├── test_layer_separation.py
│   └── test_ssot_immutability.py
└── evidence/
    └── test_lookahead_regression.py
```

---

## E. Evidence Regression Checks

### E.1 Lookahead Detection via Statistical Analysis

**Test:** `test_lookahead_regression_tp_sl_extremes()`

**Objective:** Detect suspicious clustering of TP/SL fills at bar extremes

**Methodology:**
- For each TP fill (LONG), measure: `distance_from_high = bar_high - fill_price`
- For each SL fill (LONG), measure: `distance_from_low = fill_price - bar_low`
- Compute distribution of distances
- Flag if >80% of fills are within 1 tick of extreme (suspicious)

**Assertions:**
```python
tp_fills_long = filled_orders[
    (filled_orders.exit_reason == "TP") &
    (filled_orders.side == "LONG")
]

distances = []
for fill in tp_fills_long.itertuples():
    bar = exec_bars.loc[fill.bar_ts_exec]
    distance = bar.high - fill.fill_price
    distances.append(distance)

pct_at_extreme = sum(d < 0.01 for d in distances) / len(distances)

assert pct_at_extreme < 0.80, \
    f"Lookahead suspected: {pct_at_extreme:.1%} of TP fills at bar high"
```

**Outcome:**
- If fails: Mark evidence with `LOOKAHEAD_SUSPECTED`
- Downgrade to `WARN` or `FAIL` depending on threshold

**Invariants tested:** `EVID-1` (evidence quality)

---

**Test:** `test_lookahead_regression_fills_before_signal_close()`

**Objective:** Detect fills occurring before signal bar close (severe lookahead)

**Setup:**
- For each trade, get signal timestamp and entry fill timestamp
- Verify entry fill occurs strictly after signal bar close

**Assertions:**
```python
for trade in trades.itertuples():
    order = orders[orders.order_id == trade.order_id].iloc[0]
    entry_fill = filled_orders[
        (filled_orders.trade_id == trade.trade_id) &
        (filled_orders.fill_type == "ENTRY")
    ].iloc[0]

    signal_bar_close_ts = order.created_from_ts + signal_tf_timedelta

    assert entry_fill.fill_ts > signal_bar_close_ts, \
        f"Lookahead: Entry fill {entry_fill.fill_ts} before signal close {signal_bar_close_ts}"
```

**Invariants tested:** `EXEC-1` (no lookahead)

---

### E.2 Warn-Only Thresholds

Some evidence checks should warn but not fail builds:

**Warn conditions:**
- `NO_EXEC_BARS_M1`: Exec bars not persisted (historical runs)
- `LOOKAHEAD_SUSPECTED` with low confidence (<60%)
- Single-trade anomalies in otherwise clean runs

**Fail conditions:**
- `RTH_VIOLATION` without `allow_extended_hours=true`
- `FILL_OUTSIDE_BAR` (price plausibility failure)
- Systemic lookahead (>30% trades flagged)

---

## F. Implementation Timeline (Non-Normative)

### Phase 1: Foundation (Week 1-2)
- [ ] Create synthetic data generator
- [ ] Implement unit tests for signal grid, RTH filter
- [ ] Create fixture run for integration tests

### Phase 2: Core Contract Tests (Week 3-4)
- [ ] Implement earliest-touch tests
- [ ] Implement fill plausibility tests
- [ ] Implement deterministic ID tests
- [ ] Implement lineage integrity tests

### Phase 3: Integration & Architecture (Week 5)
- [ ] Implement acceptance criteria tests
- [ ] Implement architecture separation tests
- [ ] Set up CI gate job

### Phase 4: Evidence & Regression (Week 6)
- [ ] Implement lookahead detection tests
- [ ] Set up evidence regression monitoring
- [ ] Document evidence degradation policies

---

## G. Success Metrics

**Contract enforcement is successful when:**

1. **Coverage:** All 23 invariants from contract have corresponding tests
2. **Speed:** Contract gate runs in <5 minutes
3. **Reliability:** Zero false positives in past 30 days
4. **Adoption:** 100% of new backtests pass contract gate before merge
5. **Auditability:** Every contract violation has traceable evidence code

---

**Document Version:** 1.0
**Last Updated:** 2025-12-24
**Maintaining Team:** Trading Platform Engineering
