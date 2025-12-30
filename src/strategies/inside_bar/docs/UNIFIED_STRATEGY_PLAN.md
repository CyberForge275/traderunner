# Unified InsideBar Strategy - Implementation Plan

> **Critical Requirement:** ZERO deviation between Backtest and Live
>
> Any difference = Backtest results INVALID

---

## 🎯 Objectives

### Primary Goal
**Single source of truth for InsideBar strategy logic**

### Success Criteria
1. ✅ Parity Test: 100% identical signals for same input data
2. ✅ Zero code duplication for core logic
3. ✅ Single configuration file controls both systems
4. ✅ Automated CI/CD validation

---

## 📁 Proposed File Structure

```
traderunner/src/strategies/inside_bar/
├── __init__.py                 # Public exports
├── core.py                     # ⭐ SINGLE SOURCE OF TRUTH
├── config.py                   # Configuration schema
├── backtest_adapter.py         # Backtest I/O adapter
└── tests/
    ├── test_core.py            # Unit tests for core
    ├── test_parity.py          # ⭐ CRITICAL: Backtest vs Live
    └── fixtures/
        └── test_data.parquet   # Sample M5 candles

marketdata-stream/src/live_trading/
├── inside_bar_detector.py      # Live I/O adapter (refactored)
└── tests/
    └── test_live_adapter.py    # Integration tests

config/ (symlinked between projects)
└── inside_bar.yaml             # ⭐ SINGLE CONFIG FILE
```

---

## 📋 Implementation Phases

### Phase 1: Core Extraction (Day 1)

**Goal:** Extract all shared logic into `core.py`

#### 1.1 Create Core Module

**File:** `traderunner/src/strategies/inside_bar/core.py`

```python
"""
InsideBar Strategy Core Logic
Single source of truth for pattern detection and signal generation.

CRITICAL: Any change here affects BOTH backtest and live trading.
ALWAYS run parity tests after modifications.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from decimal import Decimal


@dataclass
class InsideBarConfig:
    """Validated configuration for InsideBar strategy."""
    atr_period: int = 14
    risk_reward_ratio: float = 2.0
    min_mother_bar_size: float = 0.5
    breakout_confirmation: bool = True
    inside_bar_mode: str = "inclusive"

    # Live-specific (ignored in backtest)
    lookback_candles: int = 50
    max_pattern_age_candles: int = 12
    max_deviation_atr: float = 3.0

    def validate(self):
        """Validate configuration parameters."""
        assert self.atr_period > 0, "ATR period must be positive"
        assert self.risk_reward_ratio > 0, "Risk/reward must be positive"
        assert self.inside_bar_mode in ["inclusive", "strict"], "Invalid mode"


@dataclass
class RawSignal:
    """Raw signal output from core (format-agnostic)."""
    timestamp: pd.Timestamp
    side: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    metadata: Dict[str, Any]


class InsideBarCore:
    """
    Core InsideBar strategy logic.

    This class contains ALL pattern detection and signal generation logic.
    It is used by BOTH backtesting and live trading adapters.

    Design principles:
    1. Pure functions where possible
    2. No I/O (database, files, etc.)
    3. Returns format-agnostic data structures
    4. Extensively tested
    """

    def __init__(self, config: InsideBarConfig):
        """Initialize with validated config."""
        config.validate()
        self.config = config

    def calculate_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Average True Range.

        Args:
            df: DataFrame with columns: open, high, low, close

        Returns:
            DataFrame with added 'atr' column
        """
        df = df.copy()

        # Previous close
        df['prev_close'] = df['close'].shift(1)

        # True Range components
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        # ATR
        df['atr'] = df['true_range'].rolling(
            window=self.config.atr_period
        ).mean()

        return df

    def detect_inside_bars(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect inside bar patterns.

        Args:
            df: DataFrame with OHLC data and 'atr' column

        Returns:
            DataFrame with columns:
            - is_inside_bar: bool
            - mother_bar_high: float
            - mother_bar_low: float
        """
        df = df.copy()

        # Previous bar values
        df['prev_high'] = df['high'].shift(1)
        df['prev_low'] = df['low'].shift(1)
        df['prev_range'] = df['prev_high'] - df['prev_low']

        # Inside bar condition
        if self.config.inside_bar_mode == "strict":
            inside_mask = (
                (df['high'] < df['prev_high']) &
                (df['low'] > df['prev_low'])
            )
        else:  # inclusive
            inside_mask = (
                (df['high'] <= df['prev_high']) &
                (df['low'] >= df['prev_low'])
            )

        # Ensure previous bar exists
        inside_mask &= df['prev_high'].notna() & df['prev_low'].notna()

        # Minimum mother bar size filter
        if self.config.min_mother_bar_size > 0:
            size_ok = df['prev_range'] >= (
                self.config.min_mother_bar_size * df['atr']
            )
            inside_mask &= size_ok.fillna(False)

        df['is_inside_bar'] = inside_mask
        df['mother_bar_high'] = df['prev_high'].where(inside_mask)
        df['mother_bar_low'] = df['prev_low'].where(inside_mask)

        return df

    def generate_signals(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> List[RawSignal]:
        """
        Generate trading signals from pattern data.

        Args:
            df: DataFrame with inside bar detection results
            symbol: Trading symbol

        Returns:
            List of RawSignal objects
        """
        signals = []

        # Find inside bars
        inside_mask = df['is_inside_bar'].fillna(False)
        if not inside_mask.any():
            return signals

        # For each potential breakout candle
        for idx in range(len(df)):
            if idx == 0:
                continue

            current = df.iloc[idx]

            # Find most recent inside bar before current
            recent_inside = df.iloc[:idx][inside_mask[:idx]]
            if recent_inside.empty:
                continue

            last_inside = recent_inside.iloc[-1]
            mother_high = last_inside['mother_bar_high']
            mother_low = last_inside['mother_bar_low']

            if pd.isna(mother_high) or pd.isna(mother_low):
                continue

            # Check for breakout
            if self.config.breakout_confirmation:
                compare_high = current['close']
                compare_low = current['close']
            else:
                compare_high = current['high']
                compare_low = current['low']

            # LONG breakout
            if compare_high > mother_high:
                entry = float(mother_high)
                sl = float(mother_low)
                risk = entry - sl
                tp = entry + (risk * self.config.risk_reward_ratio)

                signal = RawSignal(
                    timestamp=current['timestamp'],
                    side='BUY',
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    metadata={
                        'pattern': 'inside_bar_breakout',
                        'mother_high': float(mother_high),
                        'mother_low': float(mother_low),
                        'atr': float(current['atr']),
                        'risk': risk,
                        'reward': risk * self.config.risk_reward_ratio
                    }
                )
                signals.append(signal)

                # Only one signal per pattern
                inside_mask.iloc[:idx] = False

            # SHORT breakout
            elif compare_low < mother_low:
                entry = float(mother_low)
                sl = float(mother_high)
                risk = sl - entry
                tp = entry - (risk * self.config.risk_reward_ratio)

                signal = RawSignal(
                    timestamp=current['timestamp'],
                    side='SELL',
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    metadata={
                        'pattern': 'inside_bar_breakout',
                        'mother_high': float(mother_high),
                        'mother_low': float(mother_low),
                        'atr': float(current['atr']),
                        'risk': risk,
                        'reward': risk * self.config.risk_reward_ratio
                    }
                )
                signals.append(signal)

                # Only one signal per pattern
                inside_mask.iloc[:idx] = False

        return signals

    def process_data(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> List[RawSignal]:
        """
        Complete pipeline: ATR → Pattern → Signals.

        This is the main entry point for both adapters.
        """
        # Validate input
        required = ['timestamp', 'open', 'high', 'low', 'close']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        # Pipeline
        df = self.calculate_atr(df)
        df = self.detect_inside_bars(df)
        signals = self.generate_signals(df, symbol)

        return signals
```

#### 1.2 Create Config Schema

**File:** `traderunner/src/strategies/inside_bar/config.py`

```python
"""Configuration management for InsideBar strategy."""
import yaml
from pathlib import Path
from .core import InsideBarConfig


def load_config(config_path: Path) -> InsideBarConfig:
    """Load configuration from YAML file."""
    with open(config_path) as f:
        data = yaml.safe_load(f)

    params = data.get('parameters', {})
    return InsideBarConfig(**params)


def get_default_config_path() -> Path:
    """Get path to default config file."""
    # Try to find config in standard locations
    candidates = [
        Path(__file__).parent.parent.parent.parent / 'config' / 'inside_bar.yaml',
        Path('/opt/trading/traderunner/config/inside_bar.yaml'),
        Path.home() / '.trading' / 'config' / 'inside_bar.yaml',
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(f"Config file not found in: {candidates}")
```

---

### Phase 2: Adapter Refactoring (Day 2)

#### 2.1 Backtest Adapter

**File:** `traderunner/src/strategies/inside_bar/backtest_adapter.py`

```python
"""Backtest adapter for InsideBar strategy."""
from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, Signal
from .core import InsideBarCore, InsideBarConfig, RawSignal


class InsideBarStrategy(BaseStrategy):
    """InsideBar strategy for backtesting (uses core logic)."""

    @property
    def name(self) -> str:
        return "inside_bar"

    def generate_signals(
        self,
        data: pd.DataFrame,
        symbol: str,
        config: Dict[str, Any]
    ) -> List[Signal]:
        """
        Generate signals for backtesting.

        This is just an I/O adapter - all logic is in core.py
        """
        # Validate input
        self.validate_data(data)
        df = self.preprocess_data(data.copy())

        # Create config
        strategy_config = InsideBarConfig(**config)

        # Use core logic
        core = InsideBarCore(strategy_config)
        raw_signals = core.process_data(df, symbol)

        # Convert to Backtest Signal objects
        signals = []
        for raw in raw_signals:
            signal = self.create_signal(
                timestamp=raw.timestamp,
                symbol=symbol,
                signal_type=raw.side,  # "BUY" or "SELL"
                confidence=0.8,
                entry_price=raw.entry_price,
                stop_loss=raw.stop_loss,
                take_profit=raw.take_profit,
                **raw.metadata
            )
            signals.append(signal)

        return signals
```

#### 2.2 Live Adapter

**File:** `marketdata-stream/src/live_trading/inside_bar_detector.py` (REFACTORED)

```python
"""Live detector for InsideBar (uses core logic from traderunner)."""
import sys
from pathlib import Path

# Import core from traderunner
TRADERUNNER_PATH = Path('/opt/trading/traderunner')
if TRADERUNNER_PATH.exists():
    sys.path.insert(0, str(TRADERUNNER_PATH))

from src.strategies.inside_bar.core import InsideBarCore, InsideBarConfig
from src.strategies.inside_bar.config import get_default_config_path, load_config

from .base import BaseLiveStrategyDetector
from ..contracts import SignalOutputSpec


class InsideBarDetector(BaseLiveStrategyDetector):
    """Live detector - uses core logic from traderunner."""

    def __init__(self):
        # Load config from YAML
        config_path = get_default_config_path()
        self.strategy_config = load_config(config_path)

        # Create core
        self.core = InsideBarCore(self.strategy_config)

        super().__init__(
            intervals=["M5"],
            buffer_size=200
        )

    async def detect_patterns(self, df, symbol, interval):
        """
        Detect patterns using core logic.

        This is just an I/O adapter - all logic is in core.py
        """
        # Use core logic
        raw_signals = self.core.process_data(df, symbol)

        # Convert to SignalOutputSpec
        signals = []
        for raw in raw_signals:
            if raw.side == 'BUY':
                signal = SignalOutputSpec(
                    symbol=symbol,
                    timestamp=raw.timestamp,
                    strategy='inside_bar',
                    strategy_version='2.0.0',
                    long_entry=Decimal(str(raw.entry_price)),
                    short_entry=None,
                    sl_long=Decimal(str(raw.stop_loss)),
                    sl_short=None,
                    tp_long=Decimal(str(raw.take_profit)),
                    tp_short=None,
                    setup='inside_bar_breakout',
                    score=0.8,
                    metadata=raw.metadata
                )
            else:  # SELL
                signal = SignalOutputSpec(
                    symbol=symbol,
                    timestamp=raw.timestamp,
                    strategy='inside_bar',
                    strategy_version='2.0.0',
                    long_entry=None,
                    short_entry=Decimal(str(raw.entry_price)),
                    sl_long=None,
                    sl_short=Decimal(str(raw.stop_loss)),
                    tp_long=None,
                    tp_short=Decimal(str(raw.take_profit)),
                    setup='inside_bar_breakout',
                    score=0.8,
                    metadata=raw.metadata
                )
            signals.append(signal)

        return signals
```

---

### Phase 3: Testing & Validation (Day 3)

#### 3.1 Critical Parity Test

**File:** `traderunner/src/strategies/inside_bar/tests/test_parity.py`

```python
"""
CRITICAL TEST: Backtest vs Live Parity

This test MUST pass at all times. Any failure means
backtest results are INVALID.
"""
import pytest
import pandas as pd
from decimal import Decimal

from ..core import InsideBarCore, InsideBarConfig
from ..backtest_adapter import InsideBarStrategy
from marketdata_stream.src.live_trading.inside_bar_detector import InsideBarDetector


class TestBacktestLiveParity:
    """Verify 100% identical results between backtest and live."""

    @pytest.fixture
    def test_data(self):
        """Load real M5 candles for APP from Nov 24."""
        # Load from artifacts or generate deterministic data
        return pd.read_parquet('fixtures/APP_2025-11-24_M5.parquet')

    @pytest.fixture
    def config(self):
        """Shared configuration."""
        return {
            'atr_period': 14,
            'risk_reward_ratio': 2.0,
            'min_mother_bar_size': 0.5,
            'breakout_confirmation': True,
            'inside_bar_mode': 'inclusive'
        }

    def test_same_number_of_signals(self, test_data, config):
        """Both systems MUST generate same number of signals."""
        # Backtest
        backtest = InsideBarStrategy()
        backtest_signals = backtest.generate_signals(
            test_data, 'APP', config
        )

        # Live
        live = InsideBarDetector()
        live_signals = await live.detect_patterns(
            test_data, 'APP', 'M5'
        )

        assert len(backtest_signals) == len(live_signals), \
            f"Signal count mismatch: {len(backtest_signals)} vs {len(live_signals)}"

    def test_identical_entry_prices(self, test_data, config):
        """Entry prices MUST be identical."""
        backtest = InsideBarStrategy()
        backtest_signals = backtest.generate_signals(test_data, 'APP', config)

        live = InsideBarDetector()
        live_signals = await live.detect_patterns(test_data, 'APP', 'M5')

        for bs, ls in zip(backtest_signals, live_signals):
            assert bs.entry_price == float(ls.long_entry or ls.short_entry), \
                f"Entry price mismatch: {bs.entry_price} vs {ls.long_entry or ls.short_entry}"

    def test_identical_stop_loss(self, test_data, config):
        """Stop losses MUST be identical."""
        # Similar to above
        pass

    def test_identical_take_profit(self, test_data, config):
        """Take profits MUST be identical."""
        # Similar to above
        pass

    def test_identical_timestamps(self, test_data, config):
        """Signal timestamps MUST be identical."""
        # Similar to above
        pass

    @pytest.mark.parametr ize("risk_reward", [1.5, 2.0, 2.5, 3.0])
    def test_parity_different_risk_rewards(self, test_data, risk_reward):
        """Test parity across different risk/reward ratios."""
        config = {
            'atr_period': 14,
            'risk_reward_ratio': risk_reward,
            'min_mother_bar_size': 0.5,
            'breakout_confirmation': True,
            'inside_bar_mode': 'inclusive'
        }

        # Run same tests as above
        self.test_same_number_of_signals(test_data, config)
        self.test_identical_entry_prices(test_data, config)
```

#### 3.2 Integration Test

```bash
# Test entire pipeline
pytest traderunner/src/strategies/inside_bar/tests/test_parity.py -v

# Expected output:
# test_same_number_of_signals PASSED ✅
# test_identical_entry_prices PASSED ✅
# test_identical_stop_loss PASSED ✅
# test_identical_take_profit PASSED ✅
# test_identical_timestamps PASSED ✅
# test_parity_different_risk_rewards[1.5] PASSED ✅
# test_parity_different_risk_rewards[2.0] PASSED ✅
# test_parity_different_risk_rewards[2.5] PASSED ✅
# test_parity_different_risk_rewards[3.0] PASSED ✅
```

---

## 🎯 Acceptance Criteria

### MUST Pass (Blocking)

- [ ] All parity tests GREEN (100% pass rate)
- [ ] Zero code duplication in pattern detection
- [ ] Single config file controls both systems
- [ ] Documentation updated

### SHOULD Have (Non-blocking)

- [ ] CI/CD pipeline runs parity tests
- [ ] Performance benchmarks (no regression)
- [ ] Migration guide for existing code

---

## 🚀 Deployment Strategy

### Step 1: Deploy to Dev
- Test with small dataset
- Verify parity

### Step 2: Parallel Run
- Run old + new side-by-side
- Compare results for 1 week

### Step 3: Switch Live
- Disable old implementations
- Enable unified core

### Step 4: Cleanup
- Remove deprecated code
- Archive for reference

---

## 📊 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Parity Test Pass Rate | 100% | CI/CD |
| Signal Count Match | 100% | Test suite |
| Entry Price Deviation | 0.00% | Max abs diff |
| SL/TP Deviation | 0.00% | Max abs diff |
| Code Duplication | 0 lines | SonarQube |

---

**Ready to start?** Let's begin with Phase 1: Core Extraction! 🚀
