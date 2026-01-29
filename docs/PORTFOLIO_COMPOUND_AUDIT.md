# Portfolio Compound Accounting Audit

**Date**: 2026-01-04  
**Scope**: Traderunner/Axiom-BT Backtest System  
**Objective**: Understand current equity/cash tracking and design clean compound accounting architecture

---

## Executive Summary

**Current State**: The backtest system has **NO centralized Portfolio/Ledger class**. Equity and cash tracking is scattered across:
- Local `cash` variable in replay engines (line-by-line updates)
- Post-facto equity derivation in `metrics.py` from trades
- Strategy-params `initial_cash` flowing through but not compounding

**Key Finding**: Position sizing uses `initial_cash` throughout the entire backtest - **NO compounding occurs**. Each trade is sized from the same starting equity, regardless of previous wins/losses.

**Impact**: This is a fundamental architecture gap preventing proper compound backtesting.

---

## 1. Code Inventory

| Area | File | Function/Class | What it does | Inputs/Outputs | SSOT? | Coupling |
|:-----|:-----|:---------------|:-------------|:---------------|:------|:---------|
| **Initial Cash Setup** |
| Config | `src/core/settings/constants.py` | `DEFAULT_INITIAL_CASH` | Default value = 10000.0 | Constant | No | Low |
| Runner Entry | `src/axiom_bt/runner.py:87` | Run config parsing | Extract from config | `cfg.get("initial_cash")` | No | Low |
| **Order Sizing (CRITICAL)** |
| Sizing Core | `src/trade/position_sizing.py` | `qty_risk_based()` | Calculate qty based on risk | `equity, risk_pct, prices` → `qty` | **Yes** | Med |
| Sizing Core | `src/trade/position_sizing.py` | `qty_pct_of_equity()` | Calculate qty as % of equity | `equity, pct, price` → `qty` | **Yes** | Low |
| Sizing Core | `src/trade/position_sizing.py` | `qty_fixed()` | Fixed quantity | `qty` → `qty` | Yes | Low |
| Order Builder | `src/trade/orders_builder.py:91-112` | `_build_args_from_params()` | Build order args, **uses initial_cash for max_notional** | `initial_cash, max_position_pct` → `max_notional` | No | **High** |
| Order Builder | `src/trade/orders_builder.py:141` | Order creation | Pass equity param | `equity=initial_cash` | No | **High** |
| **Cash/Equity Tracking** |
| Replay Engine | `src/axiom_bt/engines/replay_engine.py:310` | `simulate_insidebar_from_orders()` | Initialize cash variable | `cash = initial_cash` | No | Med |
| Replay Engine | `src/axiom_bt/engines/replay_engine.py:368` | Trade execution | **Local update**: `cash += pnl` | After each trade | No | **High** |
| Replay Engine | `src/axiom_bt/engines/replay_engine.py:561` | `simulate_orders()` (MOC) | Separate cash tracker | `cash = initial_cash` | No | Med |
| Replay Engine | `src/axiom_bt/engines/replay_engine.py:603` | MOC fee tracking | `cash -= fees` | Per fill | No | Med |
| **Equity Derivation** |
| Metrics | `src/axiom_bt/metrics.py:49` | `equity_from_trades()` | **Post-facto reconstruction** | `trades → equity_curve` | **Yes** | Low |
| Metrics | `src/axiom_bt/metrics.py:56` | Equity calc | `equity = initial_cash + pnl.cumsum()` | Cumulative sum | **Yes** | Low |
| **Portfolio State (Minimal)** |
| Risk Guards | `src/axiom_bt/risk/guards.py:27-32` | `Portfolio` (Protocol) | **Interface only** - not implemented | `cash, positions, daily_pnl, peak_equity` | No | Low |
| **Artifacts** |
| Output | `src/axiom_bt/runner.py:180` | Write equity curve | Save CSV | `equity.to_csv()` | No | Low |
| Metrics | `src/axiom_bt/metrics.py:186-187` | Compose final metrics | `initial_cash, final_cash` | From equity curve | No | Low |

---

## 2. Dataflow / Callgraph

```
USER (Dashboard/CLI)
  ↓ run_id, symbols, strategy, lookback_days
┌─────────────────────────────────────────────────────────────────┐
│   - initial_cash=10000.0 (parameter)                            │
│   - Passes to strategy.generate_signals(initial_cash=...)       │
└──────────────────┬──────────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────────┐
│ src/strategies/inside_bar/strategy.py::generate_signals()      │
│   - Receives initial_cash in config dict                        │
│   - Passes to orders_builder                                    │
└──────────────────┬──────────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────────┐
│ src/trade/orders_builder.py::_build_args_from_params()         │
│   ⚠️ SIZING HAPPENS HERE ⚠️                                    │
│   - initial_cash (static) → max_notional calc                   │
│   - max_notional = initial_cash * max_position_pct / 100        │
│   - Creates argparse.Namespace(equity=initial_cash, ...)        │
│   - NO REFERENCE TO CURRENT CASH/EQUITY                        │
└──────────────────┬──────────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────────┐
│ src/trade/position_sizing.py::qty_risk_based()                 │
│   - Uses equity parameter from args                             │
│   - equity is ALWAYS initial_cash (static)                      │
│   - Calculates qty: risk_cash / price_diff                      │
└──────────────────┬──────────────────────────────────────────────┘
                   ↓
         [Orders DataFrame created]
                   ↓
┌─────────────────────────────────────────────────────────────────┐
│ src/axiom_bt/engines/replay_engine.py::simulate_...()          │
│   ORDER LAYER → POSITION LAYER                                  │
│   - Entry: cash = initial_cash (line 310)                       │
│   - For each fill:                                              │
│     1. Match order to bar                                       │
│     2. Calculate pnl = qty * (exit - entry) - fees              │
│     3. Update local: cash += pnl (line 368)                     │
│   - Local cash is NEVER fed back to sizing                      │
└──────────────────┬──────────────────────────────────────────────┘
                   ↓
         [Trades DataFrame]
                   ↓
┌─────────────────────────────────────────────────────────────────┐
│ src/axiom_bt/metrics.py::equity_from_trades()                  │
│   PORTFOLIO LAYER (Post-facto)                                  │
│   - equity = initial_cash + trades['pnl'].cumsum()              │
│   - Creates equity_curve.csv                                    │
│   - This is DERIVED, not LIVE                                   │
└──────────────────┬──────────────────────────────────────────────┘
                   ↓
         [equity_curve.csv, metrics.json]
```

### Critical Gaps Identified

1. **Sizing ↔ Cash Disconnect**: Orders are sized at T=0 using `initial_cash`. The `cash` variable in replay_engine is updated but **never flows back** to sizing.

2. **No Portfolio SSOT**: `Portfolio` exists only as a Protocol in guards.py. No actual implementation tracks state across trades.

3. **Post-facto Equity**: `equity_curve.csv` is reconstructed from trades **after** the backtest completes. It's not used during execution.

---

## 3. Current Behavior Hypothesis

### How "Compound" Currently Works (Spoiler: It Doesn't)

**Hypothesis**: Position sizing is **static** - all trades use `initial_cash` for calculations.

**Evidence**:

1. **Line 91-112** in `orders_builder.py`:
   ```python
   initial_cash = float(strategy_params.get("initial_cash", DEFAULT_INITIAL_CASH))
   # ...
   max_notional = initial_cash * max_position_pct / 100.0
   # ...
   equity=initial_cash  # ← STATIC, NEVER UPDATED
   ```

2. **Line 310** in `replay_engine.py`:
   ```python
   cash = initial_cash  # Local variable
   ```

3. **Line 368** in `replay_engine.py`:
   ```python
   cash += pnl  # Updated locally, but...
   # ...never passed back to sizing
   ```

4. **Line 56** in `metrics.py`:
   ```python
   eq["equity"] = float(initial_cash) + pnl.cumsum()
   # This is RETROSPECTIVE calculation
   ```

### Concrete Example

- Start: $10,000
- Trade 1: +$1,000 → Cash now $11,000
- Trade 2 sizing: **Still uses $10,000** (not $11,000)
- Trade 2: +$1,000 → Cash now $12,000
- Trade 3 sizing: **Still uses $10,000** (not $12,000)

**Result**: No geometric growth. Each trade risks the same $100 (1% of $10k) regardless of account growth.

### Where Equity is Updated

| Location | When | Why | Does it affect next trade? |
|:---------|:-----|:----|:---------------------------|
| `replay_engine.py:368` | After each fill | Track for final metrics | ❌ NO |
| `metrics.py:56` | After all trades | Create equity_curve.csv | ❌ NO |
| `orders_builder.py:141` | Before any trades | Set sizing baseline | ❌ NO (static) |

**Conclusion**: The system has a "ledger" (local `cash` variable) but it's **write-only** for artifacts, not a **read-write SSOT** for decisions.

---

## 4. Capsule Design: Clean Compound Architecture

### Proposed Module Structure

```
src/axiom_bt/portfolio/
├── __init__.py
├── core.py              # PortfolioState, FillEvent, TradeEvent
├── ledger.py            # CashLedger, TransactionLog
├── accounting.py        # Account for fees, slippage, PnL
└── exposure.py          # Position tracking, max_exposure checks
```

### Core Data Models

#### PortfolioState (SSOT)
```python
@dataclass
class PortfolioState:
    """Single source of truth for portfolio state at any timestamp."""
    timestamp: pd.Timestamp
    cash: Decimal
    positions: dict[str, Decimal]  # {symbol: qty}
    fees_paid: Decimal
    equity: Decimal  # cash + sum(position_values)
    peak_equity: Decimal
    daily_pnl: Decimal
    
    @property
    def buying_power(self) -> Decimal:
        """Cash available for new positions."""
        return self.cash
    
    def position_value(self, symbol: str, price: Decimal) -> Decimal:
        """Market value of position."""
        return self.positions.get(symbol, Decimal(0)) * price
```

#### Events
```python
@dataclass
class FillEvent:
    """Immutable event: order was filled."""
    timestamp: pd.Timestamp
    symbol: str
    side: str  # 'BUY'/'SELL'
    qty: Decimal
    price: Decimal
    fees: Decimal
    slippage: Decimal
    
@dataclass
class ExitEvent:
    """Immutable event: position was closed."""
    timestamp: pd.Timestamp
    symbol: str
    entry_price: Decimal
    exit_price: Decimal
    qty: Decimal
    pnl: Decimal
    fees_total: Decimal
```

### Minimal Interfaces

#### Portfolio API
```python
class Portfolio:
    """Central ledger for backtest accounting."""
    
    def __init__(self, initial_cash: Decimal):
        self._initial_cash = initial_cash
        self._state = PortfolioState(
            timestamp=pd.Timestamp.min,
            cash=initial_cash,
            positions={},
            fees_paid=Decimal(0),
            equity=initial_cash,
            peak_equity=initial_cash,
            daily_pnl=Decimal(0)
        )
        self._ledger: list[PortfolioState] = []
    
    def apply_fill(self, event: FillEvent) -> PortfolioState:
        """
        Apply a fill event, update cash/positions.
        
        Returns new state (immutable).
        """
        new_cash = self._state.cash - (event.qty * event.price + event.fees)
        new_positions = self._state.positions.copy()
        new_positions[event.symbol] = new_positions.get(event.symbol, Decimal(0)) + event.qty
        
        new_state = PortfolioState(
            timestamp=event.timestamp,
            cash=new_cash,
            positions=new_positions,
            fees_paid=self._state.fees_paid + event.fees,
            equity=new_cash + self._position_values(new_positions),
            peak_equity=max(self._state.peak_equity, ...),
            daily_pnl=...
        )
        self._state = new_state
        self._ledger.append(new_state)
        return new_state
    
    def apply_exit(self, event: ExitEvent) -> PortfolioState:
        """Apply position close, realize PnL."""
        new_cash = self._state.cash + event.pnl - event.fees_total
        # ...
        return new_state
    
    def current_equity(self) -> Decimal:
        """Current equity (for sizing)."""
        return self._state.equity
    
    def max_buying_power(self, max_position_pct: float) -> Decimal:
        """Max $ for a single position."""
        return self._state.equity * Decimal(max_position_pct) / Decimal(100)
    
    def to_equity_curve(self) -> pd.DataFrame:
        """Export ledger as equity_curve.csv."""
        return pd.DataFrame([
            {"ts": s.timestamp, "equity": float(s.equity)}
            for s in self._ledger
        ])
```

### How Sizing Uses Current Equity

**Before (static)**:
```python
# orders_builder.py
equity = initial_cash  # Never changes
```

**After (compound)**:
```python
# orders_builder.py (modified)
equity = portfolio.current_equity()  # Live value
```

**In Engine**:
```python
# replay_engine.py
portfolio = Portfolio(initial_cash)

for fill_event in fills:
    new_state = portfolio.apply_fill(fill_event)
    # new_state.equity is now updated
```

**In Strategy** (when generating signals):
```python
# Strategy would query Portfolio for current equity
current_equity = portfolio.current_equity()
# Use for next signal's sizing
```

### Clean Separation of Concerns

| Component | Responsibility | Reads From | Writes To |
|:----------|:---------------|:-----------|:----------|
| Portfolio | Cash/Position SSOT | Events | State, Ledger |
| Engine | Execute fills | Orders, Bars | FillEvents |
| Strategy | Generate signals | Bars, Portfolio.equity | Orders |
| Accounting | PnL, Fees | FillEvents, ExitEvents | Portfolio (via events) |
| Metrics | Export artifacts | Portfolio.ledger | CSV, JSON |

---

## 5. Impact & Dependencies

### Modules That Would Read Portfolio

| Module | Current Behavior | Future Behavior |
|:-------|:-----------------|:----------------|
| `src/trade/orders_builder.py` | Uses `initial_cash` | Calls `portfolio.current_equity()` |
| `src/trade/position_sizing.py` | Receives static `equity` | Receives dynamic `equity` from Portfolio |
| `src/axiom_bt/engines/replay_engine.py` | Local `cash` variable | Creates/updates Portfolio instance |
| `src/strategies/inside_bar/strategy.py` | Passes `initial_cash` | Queries Portfolio for sizing |

### Modules That Would Generate Events

| Module | Event Type | When |
|:-------|:-----------|:-----|
| `replay_engine.py` | `FillEvent` | On order match |
| `replay_engine.py` | `ExitEvent` | On position close |
| `accounting.py` (new) | `FeeEvent`, `SlippageEvent` | On fills |

### Artifacts That Would Change

| Artifact | Current Source | Future Source | Change |
|:---------|:---------------|:---------------|:-------|
| `equity_curve.csv` | `metrics.equity_from_trades()` | `Portfolio.to_equity_curve()` | Direct export, not derived |
| `trades.csv` | Replay engine | Engine + Portfolio | Add `equity_at_entry` column |
| `metrics.json` | `initial_cash, final_cash` | `Portfolio.initial, Portfolio.final` | Same values, cleaner source |
| `run_manifest.json` | Missing equity tracking | Add `compound_mode: true` | New parameter |

### Tests Required

1. **Portfolio State Tests**
   - `test_portfolio_apply_fill_updates_cash()`
   - `test_portfolio_apply_exit_realizes_pnl()`
   - `test_portfolio_equity_includes_position_values()`
   - `test_portfolio_max_buying_power_respects_pct()`

2. **Compound Parity Tests**
   - `test_compound_vs_static_equity_divergence()` - Prove they differ
   - `test_compound_geometric_growth()`
   - `test_static_linear_growth()`

3. **Regression Tests**
   - `test_equity_curve_deterministic()` - Same seed → same results
   - `test_final_cash_matches_sum_of_pnls()` - Accounting conservation

4. **Integration Tests**
   - `test_full_backtest_with_compound()` - End-to-end
   - `test_replay_engine_uses_portfolio()`

---

## 6. Migration Plan (Mini-Steps)

### Step 1: Read-Only Wiring (Dual-Track)
**Goal**: Create Portfolio instance but don't use it for sizing yet.

**Changes**:
- Add `src/axiom_bt/portfolio/core.py` with Portfolio class
- Modify `replay_engine.py`: create Portfolio, apply events
- **Keep old `cash` variable**, run both in parallel
- Export both `equity_curve.csv` (old) and `equity_curve_v2.csv` (new)

**Risk**: Low - additive only, no behavioral change

**Acceptance**:
- Both equity curves must match exactly (within floating point tolerance)
- No test regressions

**Tests**:
- `test_portfolio_equity_matches_ledger_cash()`

---

### Step 2: Parity Check (Dual-Run Validation)
**Goal**: Prove new Portfolio accounting is identical to old method.

**Changes**:
- Add assertion in engine: `assert abs(portfolio.cash - old_cash) < 0.01`
- Run 100+ backtests, verify no assertion failures

**Risk**: Low - still validation only

**Acceptance**:
- 100% parity on existing test suite
- Diff budget: $0.00 (exact match required)

**Tests**:
- `test_parity_on_golden_backtest_runs()`

---

### Step 3: Switch Sizing Source (Enable Compound)
**Goal**: Use `portfolio.current_equity()` for sizing instead of `initial_cash`.

**Changes**:
- Modify `orders_builder.py`: accept Portfolio instance
- Replace `initial_cash` with `portfolio.current_equity()` call
- Add `compound_mode` parameter to run_manifest

**Risk**: **High** - changes trade sizing, results will diverge

**Acceptance**:
- New results show **geometric** growth pattern
- Equity curve slopes differently (compound vs linear)
- Sharpe ratio may improve (if strategy is profitable)
- **NOT** deterministic with old runs (expected divergence)

**Tests**:
- `test_compound_mode_grows_geometrically()`
- `test_profitable_strategy_compounds_faster_than_static()`

---

### Step 4: Remove Old Ledger (Cleanup)
**Goal**: Delete redundant `cash` variable from engines.

**Changes**:
- Remove local `cash` tracking in `replay_engine.py`
- Remove `equity_from_trades()` in favor of `Portfolio.to_equity_curve()`
- Update all callers

**Risk**: Low - cleanup only

**Acceptance**:
- No behavioral change vs Step 3
- Code coverage maintained

**Tests**:
- Run full regression suite

---

## Appendix: Key Code Locations

### Critical Files for Compound Implementation

1. **`src/trade/orders_builder.py:91-141`** - Where sizing happens (MUST change)
2. **`src/axiom_bt/engines/replay_engine.py:310-368`** - Cash tracking (WILL be replaced)
3. **`src/axiom_bt/metrics.py:49-56`** - Equity derivation (WILL be replaced)
4. **`src/trade/position_sizing.py:33-78`** - Qty calculation (receives equity parameter)

### Search Terms for Further Investigation

If implementing, search for:
- `initial_cash` - All hardcoded references
- `cash +=` / `cash -=` - Local ledger updates
- `equity=` - Where equity is passed
- `max_notional` - Position size caps
- `simulate_.*_from_orders` - Engine entry points

---

## Conclusion

**Current State**: Traderunner backtests are **NOT compounded**. All trades use the same `initial_cash` for sizing, resulting in linear rather than geometric equity growth.

**Root Cause**: No Portfolio SSOT exists. Cash tracking is local to engines and never feeds back to sizing logic.

**Recommended Path**: Implement Portfolio capsule in 4 mini-steps, starting with read-only dual-tracking to ensure parity before switching sizing source.

**Effort Estimate**: 
- Step 1-2: ~2-3 days (safe, reversible)
- Step 3: ~1-2 days (risky, requires validation)
- Step 4: ~1 day (cleanup)

**Total**: ~5-7 days for full compound capability

---

*End of Report*
