# Pre-Paper Runtime History Loading

## Overview

Pre-Paper runtime enables **live strategy execution** using the **same Backtest-Atom** but with **hybrid data sourcing**: historical (from cache) + realtime (from WebSocket).

**Core Promise:** Strategy execution only when history is **SUFFICIENT**. Otherwise: **NO-SIGNALS / DEGRADED** with clear reason.

## Mission

Build runtime history loading that:
1. **Preserves data segregation** (no backtest parquet writes)
2. **Enforces manifest SSOT** (promotion contract)
3. **Provides clear degradation** (NO-SIGNALS when insufficient)
4. **Enables auditability** (pre_paper artifacts)

## Architecture

### Package Structure

```
src/pre_paper/
├── __init__.py
├── runtime_history_loader.py    # ensure_history() + cache management
├── historical_provider.py        # Interface for fetching missing ranges
├── pre_paper_runner.py           # Orchestrator (WebSocket + strategy)
└── cache/
    ├── __init__.py
    └── sqlite_cache.py           # pre_paper_cache.db wrapper

artifacts/pre_paper_cache/
└── pre_paper_cache.db            # Runtime history buffer (WRITABLE)

artifacts/pre_paper/<run_id>/
├── pre_paper_manifest.json       # Audit trail (references backtest manifest)
├── pre_paper.log                 # Runtime logs
└── signals/                      # Optional outputs
```

### Data Flow

```
┌─────────────────┐
│ Backtest Atom   │ (promotion contract)
│ run_manifest    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Pre-Paper Runner                        │
│ - Load manifest (SSOT)                  │
│ - Calculate required history            │
│ - Check cache (pre_paper_cache.db)      │
└─────────┬───────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│ ensure_history()                        │
│ - Cache check                           │
│ - Backfill missing ranges              │
│ - Status: SUFFICIENT / LOADING / DEGRADED │
└─────────┬───────────────────────────────┘
          │
          ▼
    ┌─────┴─────┐
    │           │
    ▼           ▼
SUFFICIENT   DEGRADED
    │           │
    ▼           ▼
Strategy    NO-SIGNALS
Execute     (logged)
```

## Data Segregation Rules

### Read-Only Sources

**Backtest Parquet** (historical baseline):
- Location: `data/intraday/M5/*.parquet`
- Access: **READ-ONLY** in Pre-Paper
- Purpose: Initial warm-start if cache empty

**Live DB** (if exists):
- Location: `live_trading.db` (separate system)
- Access: **READ-ONLY** in Pre-Paper
- Purpose: Optional recent history overlay

### Writable Cache

**Pre-Paper Cache DB**:
- Location: `artifacts/pre_paper_cache/pre_paper_cache.db`
- Access: **WRITE** (Pre-Paper runtime only)
- Schema:
  ```sql
  CREATE TABLE bars (
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    ts INTEGER NOT NULL,  -- Unix timestamp (UTC)
    market_tz TEXT NOT NULL,  -- Always 'America/New_York'
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    source TEXT,  -- 'historical' | 'websocket' | 'backfill'
    inserted_at INTEGER NOT NULL,  -- Unix timestamp
    PRIMARY KEY (symbol, tf, ts)
  );
  
  CREATE INDEX idx_bars_range ON bars(symbol, tf, ts);
  ```

**Invariants:**
- No duplicates (PRIMARY KEY enforced)
- Monotonic retrieval (`ORDER BY ts`)
- TZ normalization (store UTC, document market_tz)
- Source tracking (historical vs websocket)

## Manifest SSOT Promotion Contract

### Backtest Atom → Pre-Paper

Pre-Paper configuration is **derived entirely** from `run_manifest.json`:

```python
# Load approved backtest atom
manifest = load_manifest("artifacts/backtests/251215_144939_HOOD_15m_100d/run_manifest.json")

# Extract REQUIRED configuration
symbol = manifest["data"]["symbol"]              # HOOD
base_tf = manifest["data"]["base_tf_used"]       # M5 (CRITICAL for history calc)
requested_tf = manifest["data"]["requested_tf"]  # M15
params = manifest["params"]                      # Strategy params

# Calculate required history from params
lookback_candles = params["lookback_candles"]    # 50
max_pattern_age = params["max_pattern_age_candles"]  # 5
safety_margin = 10  # Configurable

required_bars = lookback_candles + max_pattern_age + safety_margin  # 65
```

**NO ad-hoc params** in Pre-Paper. **NO UI overrides**. Manifest is the contract.

## ensure_history() Contract

### Interface

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List
import pandas as pd

class HistoryStatus(Enum):
    """Runtime history status."""
    SUFFICIENT = "sufficient"    # Ready for strategy execution
    LOADING = "loading"          # Backfilling in progress
    DEGRADED = "degraded"        # Cannot satisfy requirement

@dataclass
class DateRange:
    """Timestamp range for gaps."""
    start: pd.Timestamp
    end: pd.Timestamp
    
    def to_dict(self):
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat()
        }

@dataclass
class HistoryCheckResult:
    """
    Result of runtime history check.
    
    Strategy execution is ONLY allowed if status == SUFFICIENT.
    """
    status: HistoryStatus
    symbol: str
    tf: str
    base_tf_used: str  # For history calculation
    
    # Required window (from manifest params)
    required_start_ts: pd.Timestamp  # market_tz
    required_end_ts: pd.Timestamp    # market_tz
    
    # Cached window (from pre_paper_cache.db)
    cached_start_ts: Optional[pd.Timestamp]
    cached_end_ts: Optional[pd.Timestamp]
    
    # Gaps (if any)
    gaps: List[DateRange]
    
    # Backfill status
    fetch_attempted: bool
    fetch_success: bool
    
    # Degradation reason
    reason: Optional[str]
    
    def to_dict(self):
        return {
            "status": self.status.value,
            "symbol": self.symbol,
            "tf": self.tf,
            "base_tf_used": self.base_tf_used,
            "required_window": {
                "start": self.required_start_ts.isoformat(),
                "end": self.required_end_ts.isoformat()
            },
            "cached_window": {
                "start": self.cached_start_ts.isoformat() if self.cached_start_ts else None,
                "end": self.cached_end_ts.isoformat() if self.cached_end_ts else None
            },
            "gaps": [g.to_dict() for g in self.gaps],
            "fetch_attempted": self.fetch_attempted,
            "fetch_success": self.fetch_success,
            "reason": self.reason
        }

def ensure_history(
    symbol: str,
    tf: str,
    base_tf_used: str,
    required_start_ts: pd.Timestamp,
    required_end_ts: pd.Timestamp,
    cache_db_path: Path,
    historical_provider: Optional[HistoricalProvider] = None,
    auto_backfill: bool = False
) -> HistoryCheckResult:
    """
    Ensure runtime history is sufficient for strategy execution.
    
    Workflow:
    1. Check pre_paper_cache.db for required window
    2. If complete → SUFFICIENT
    3. If gaps:
       - If auto_backfill=True: fetch missing ranges
       - Else: DEGRADED
    4. Return HistoryCheckResult
    
    Args:
        symbol: Stock symbol
        tf: Target timeframe (M5/M15)
        base_tf_used: Base timeframe from manifest
        required_start_ts: Required start (market_tz)
        required_end_ts: Required end (market_tz)
        cache_db_path: Path to pre_paper_cache.db
        historical_provider: Provider for backfilling
        auto_backfill: Enable automatic backfill
    
    Returns:
        HistoryCheckResult with status
    """
    pass  # Implementation in Commit 5.2
```

### Historical Provider Interface

```python
from typing import Protocol

class HistoricalProvider(Protocol):
    """
    Protocol for fetching historical data.
    
    Implementations can use:
    - EODHD API
    - Backtest parquet (read-only)
    - Other providers
    """
    
    def fetch_bars(
        self,
        symbol: str,
        tf: str,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp
    ) -> pd.DataFrame:
        """
        Fetch bars for given range.
        
        Returns:
            DataFrame with OHLCV data (timezone-aware index)
        """
        ...
```

## Runtime Flow

### 1. Startup / Symbol Subscribe

```python
# Load approved backtest atom
manifest = load_manifest("artifacts/backtests/<run_id>/run_manifest.json")

# Extract config (SSOT)
symbol = manifest["data"]["symbol"]
base_tf = manifest["data"]["base_tf_used"]
params = manifest["params"]

# Calculate required history
required_bars = params["lookback_candles"] + params["max_pattern_age_candles"] + 10
bar_duration = pd.Timedelta(minutes=5)  # For M5
required_start_ts = now - (required_bars * bar_duration)

# Check history
history_result = ensure_history(
    symbol=symbol,
    tf=base_tf,
    base_tf_used=base_tf,
    required_start_ts=required_start_ts,
    required_end_ts=now,
    cache_db_path=Path("artifacts/pre_paper_cache/pre_paper_cache.db"),
    auto_backfill=True
)

if history_result.status == HistoryStatus.SUFFICIENT:
    logger.info(f"History SUFFICIENT for {symbol} {base_tf}")
    # Proceed to strategy execution
elif history_result.status == HistoryStatus.LOADING:
    logger.warning(f"History LOADING for {symbol} {base_tf}")
    # Emit NO-SIGNALS, wait for backfill
else:  # DEGRADED
    logger.error(f"History DEGRADED for {symbol} {base_tf}: {history_result.reason}")
    # Emit NO-SIGNALS, log reason
```

### 2. WebSocket Bar Append

```python
def on_bar_received(bar: dict):
    """Handle incoming WebSocket bar."""
    # Append to cache
    cache.append_bar(
        symbol=bar["symbol"],
        tf=bar["tf"],
        ts=bar["timestamp"],
        ohlcv=bar["ohlcv"],
        source="websocket"
    )
    
    # Re-check history status
    history_result = ensure_history(...)
    
    if history_result.status == HistoryStatus.SUFFICIENT:
        # Window now complete → enable strategy
        logger.info("Window complete, enabling strategy")
    else:
        # Still degraded → continue NO-SIGNALS
        logger.debug("Window still incomplete")
```

### 3. Strategy Execution

```python
def run_strategy(symbol: str, tf: str):
    """Run strategy (ONLY if history is SUFFICIENT)."""
    # Check history FIRST
    history_result = ensure_history(...)
    
    if history_result.status != HistoryStatus.SUFFICIENT:
        # STRICT: No signals when history insufficient
        logger.warning(f"NO-SIGNALS: {history_result.reason}")
        return []  # Empty signals
    
    # Load series from cache
    df = cache.get_bars(symbol, tf, required_start_ts, required_end_ts)
    
    # Execute strategy
    signals = strategy.detect_patterns(df)
    
    return signals
```

## Pre-Paper Artifacts

Every Pre-Paper run creates artifacts for audit:

### Directory Structure

```
artifacts/pre_paper/<run_id>/
├── pre_paper_manifest.json
├── pre_paper.log
├── history_check_results.json
└── signals/  (optional)
```

### pre_paper_manifest.json

```json
{
  "identity": {
    "run_id": "pre_paper_251216_150000_HOOD_M5",
    "timestamp_utc": "2025-12-16T15:00:00Z",
    "commit_hash": "abc123def456",
    "market_tz": "America/New_York"
  },
  "backtest_atom": {
    "source_run_id": "251215_144939_HOOD_15m_100d",
    "manifest_path": "artifacts/backtests/251215_144939_HOOD_15m_100d/run_manifest.json",
    "impl_version": "1.0.0",
    "profile_version": "default"
  },
  "runtime_config": {
    "symbol": "HOOD",
    "base_tf_used": "M5",
    "required_bars": 65,
    "auto_backfill_enabled": true
  },
  "history_status": {
    "initial_check": {
      "status": "loading",
      "gaps": [{"start": "...", "end": "..."}]
    },
    "final_check": {
      "status": "sufficient",
      "gaps": []
    }
  },
  "execution_summary": {
    "signals_emitted": 12,
    "no_signals_periods": 3,
    "degraded_periods": 1
  }
}
```

## Golden Skip Policy

### Development / INT Environment

**Default behavior** (REQUIRE_GOLDEN_DATA not set):
- Golden tests **skip** when APP data unavailable
- Allows development without full dataset
- Test output: `SKIPPED (APP M5 data not available)`

### Promotion / Production Environment

**Strict mode** (REQUIRE_GOLDEN_DATA=1):
- Golden tests **FAIL** when APP data unavailable
- Blocks promotion until golden data present
- Test output: `FAILED: Golden data missing (promotion blocked)`

### Implementation

```python
# tests/test_golden_backtest_atom.py

import os

def test_golden_atom_app_m5_inside_bar(tmp_path):
    """Golden Atom test with promotion policy."""
    result = minimal_backtest_with_gates(...)
    
    # Check if data unavailable
    if result.status == RunStatus.FAILED_PRECONDITION and \
       result.reason == FailureReason.DATA_COVERAGE_GAP:
        
        # Promotion mode: FAIL explicitly
        if os.getenv("REQUIRE_GOLDEN_DATA") == "1":
            pytest.fail(
                "Golden data missing (promotion blocked). "
                f"Expected APP M5 data for range: {result.details.get('gap')}"
            )
        
        # Dev mode: SKIP
        pytest.skip(f"APP M5 data not available: {result.details.get('gap')}")
    
    # Data available: normal assertions
    assert result.status == RunStatus.SUCCESS
    # ...
```

### Usage

```bash
# Development (allow skips)
pytest tests/test_golden_backtest_atom.py -m golden

# Promotion (require data)
REQUIRE_GOLDEN_DATA=1 pytest tests/test_golden_backtest_atom.py -m golden
```

## Testing Strategy

### Unit Tests

**test_runtime_history_warm_start.py:**

1. **test_warm_start_fetches_missing_range_and_becomes_sufficient()**
   - Cache has partial bars
   - Provider returns missing bars
   - Status: LOADING → SUFFICIENT

2. **test_incomplete_history_keeps_degraded_and_no_signals()**
   - Provider fails or returns empty
   - Status: DEGRADED
   - Strategy emits NO-SIGNALS

3. **test_no_cross_contamination_never_writes_backtest_parquet()**
   - Patch file system / parquet write calls
   - Assert no writes under `data/intraday/` or `artifacts/backtests/`

4. **test_cache_append_websocket_bars_completes_window()**
   - Cache initially incomplete
   - Append WebSocket bars
   - Window becomes complete → SUFFICIENT

### Integration Tests

- End-to-end: Load manifest → check history → strategy execution
- WebSocket simulation: Bar stream → cache update → strategy trigger
- Degradation scenarios: Missing provider, network failures

## Invariants

1. **Data Segregation**: Pre-Paper NEVER writes to backtest parquet or live DB
2. **Manifest SSOT**: All Pre-Paper config derived from run_manifest.json
3. **NO-SIGNALS Enforcement**: Strategy execution blocked unless SUFFICIENT
4. **Market TZ**: Always America/New_York (immutable)
5. **Cache Integrity**: No duplicate timestamps, monotonic retrieval
6. **Auditability**: All Pre-Paper runs create manifest + logs
7. **Golden Policy**: REQUIRE_GOLDEN_DATA=1 blocks promotion without data

## Future Work (Phase 6+)

- **Multi-symbol support**: Parallel history loading
- **Ring buffer optimization**: Efficient series updates
- **SLA monitoring**: Runtime data quality checks
- **Failover**: Graceful degradation on provider outages
- **Performance**: Async backfill, batched cache writes

---

**Phase 5 Deliverables:**
- ✅ Design doc (this file)
- ⏳ runtime_history_loader.py + sqlite_cache.py
- ⏳ pre_paper_runner.py (orchestrator)
- ⏳ Tests (3+ GREEN)
- ⏳ Golden skip policy (REQUIRE_GOLDEN_DATA)
