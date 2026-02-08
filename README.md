# TradeRunner - Enhanced Trading Strategy Framework

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Scalable n-strategy architecture for algorithmic trading with unified interfaces, comprehensive testing, and dashboard integration.**

## 🎯 **Overview**

TradeRunner is an enhanced trading strategy framework designed to scale from single strategies to n-strategy implementations. Built with modern Python practices, it provides:

- **🏗️ Scalable Architecture**: Protocol-based design for easy strategy expansion
- **📊 Unified Signal Format**: Standardized signal interface across all strategies
- **🔧 Configuration Management**: Pydantic-based validation and schema generation
- **🖥️ Dashboard Integration**: Streamlit-based monitoring and control interface
- **🧪 Comprehensive Testing**: Quality-first development with automated checks

> **Part of the droid-trading ecosystem** - See [Organization Overview](./Org-Overview.md) for system architecture, deployment topology, and integration with `automatictrader-api` and `marketdata-stream`.

## 🚀 **Quick Start**

### **Installation**

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/traderunner.git
cd traderunner

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Verify installation
PYTHONPATH=src python -c "from strategies import *; print('✅ TradeRunner ready!')"
```

### **Basic Usage**

```python
from strategies.base import Signal, StrategyConfig

# Create a trading signal
signal = Signal(
    timestamp="2025-01-01T10:00:00",
    symbol="AAPL",
    signal_type="LONG",
    strategy="inside_bar",

## Offline Smoke (no network)

A minimal offline sanity run that reuses an existing bars snapshot and sets `EODHD_OFFLINE=1`.

Required:
- `bars_path` must exist (pre-cached parquet/csv)

Example:
```
EODHD_OFFLINE=1 PYTHONPATH=src:. \
  python scripts/offline_smoke.py \
    --run-id smoke_YYYYMMDD_HHMM \
    --out-dir artifacts/backtests/smoke_run \
    --bars-path /path/to/bars_exec_M5_rth.parquet \
    --strategy-id insidebar_intraday \
    --strategy-version 1.0.1 \
    --symbol HOOD \
    --timeframe M5 \
    --requested-end 2025-06-01 \
    --lookback-days 30
```

Expected:
- `artifacts/backtests/<run_id>/events_intent.csv`
- `intent_hash` log line in output
