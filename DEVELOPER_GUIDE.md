# Developer Onboarding - droid-trading Ecosystem

**Last Updated:** 2024-11-28
**Quick Start Guide for Parallel Development**

---

## 🚀 Quick Clone & Setup

### 1. Clone Repositories

```bash
# Main trading framework
git clone https://github.com/CyberForge275/traderunner.git
cd traderunner
git checkout feature/v2-architecture  # Latest development branch

# Order execution service
git clone https://github.com/CyberForge275/automatictrader-api.git
cd automatictrader-api
# main branch is current

# Market data streaming
git clone https://github.com/CyberForge275/marketdata-stream.git
cd marketdata-stream
# master branch is current
```

### 2. Install Dependencies

```bash
# For each repository:
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

---

## 📁 Repository Structure

### **traderunner** (Research & Backtesting)
```
├── src/
│   ├── strategies/          # Strategy implementations
│   │   ├── rudometkin_moc/  # Rudometkin MOC strategy
│   │   └── inside_bar/      # Inside Bar strategy
│   ├── signals/             # Signal generation CLIs
│   ├── trade/               # Order export & paper trading
│   └── axiom_bt/            # Backtesting engine
├── data/samples/            # 🆕 Test datasets (see below)
├── tests/                   # Unit tests
├── docs/                    # Documentation
└── apps/                    # Streamlit dashboard
```

**Current Branch:** `feature/v2-architecture`
**Key Recent Changes:**
- Added centralized `Org-Overview.md`
- Test datasets in `data/samples/`
- Paper trading adapter

### **automatictrader-api** (Order Execution)
```
├── app.py                   # FastAPI server
├── worker.py                # Order processing worker
├── models.py                # Data models
├── storage.py               # Persistence layer
├── scripts/                 # Utility scripts
└── systemd/                 # Service files
```

**Current Branch:** `main`
**Key Features:**
- Order intent API with idempotency
- WebSocket health monitoring
- Integration with IB TWS

### **marketdata-stream** (Data Service)
```
├── src/
│   ├── providers/           # Market data providers
│   │   ├── base.py          # Provider interface
│   │   └── eodhd.py         # EODHD implementation
│   ├── aggregators/         # Candle aggregation
│   ├── api/                 # FastAPI service (optional)
│   └── runner.py            # Main entry point
├── examples/                # Integration examples
└── scripts/                 # Test scripts
```

**Current Branch:** `master`
**Key Features:**
- Provider-agnostic architecture
- WebSocket real-time streaming
- Optional candle aggregation

---

## 🎯 Current Development Status

| Component | Status | Latest Feature | Branch |
|-----------|--------|----------------|--------|
| **traderunner** | ✅ Active | Test datasets + paper trading | `feature/v2-architecture` |
| **automatictrader-api** | ✅ Migrated | GitHub migration complete | `main` |
| **marketdata-stream** | ✅ Active | EODHD provider ready | `master` |

---

## 🧪 Test Data Available

**New!** Lightweight test datasets for development without production data:

```bash
cd traderunner/data/samples/

# Daily universe data (8 symbols, 1 year)
rudometkin_test.parquet

# Intraday candles (AAPL, MSFT, TSLA - 5 days)
m1_candles/   # 1-minute
m5_candles/   # 5-minute
m15_candles/  # 15-minute
```

**Usage:**
```python
import pandas as pd

# Load test data
df = pd.read_parquet("data/samples/rudometkin_test.parquet")
m5 = pd.read_parquet("data/samples/m5_candles/AAPL.parquet")
```

See `docs/TEST_DATA.md` for full documentation.

---

## 🔀 Parallel Development Workflow

### Recommended Git Workflow

1. **Sync with latest:**
   ```bash
   git fetch origin
   git checkout feature/v2-architecture  # or main/master
   git pull origin feature/v2-architecture
   ```

2. **Create feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Work and commit:**
   ```bash
   # Make changes
   git add .
   git commit -m "feat: your feature description"
   ```

4. **Push and create PR:**
   ```bash
   git push origin feature/your-feature-name
   # Create Pull Request on GitHub
   ```

### Branch Naming Convention

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code refactoring
- `test/` - Test additions

---

## 🔗 System Integration

```
marketdata-stream (port 8090)
    ↓ (WebSocket/REST)
traderunner (strategies)
    ↓ (HTTP POST /api/v1/orderintents)
automatictrader-api (port 8080)
    ↓ (ib_insync)
Interactive Brokers TWS
```

**See:** `traderunner/Org-Overview.md` for complete architecture.

---

## 📚 Key Documentation

| File | Location | Purpose |
|------|----------|---------|
| **Org-Overview.md** | `traderunner/` | System architecture & repos |
| **TEST_DATA.md** | `traderunner/docs/` | Test dataset documentation |
| **OVERVIEW.md** | `marketdata-stream/` | Data service architecture |
| **GITHUB_MIGRATION_GUIDE.md** | `automatictrader-api/` | Migration reference |

---

## 🧪 Running Tests

```bash
# traderunner
cd traderunner
pytest tests/

# With test data
pytest tests/test_rudometkin_moc_strategy.py

# automatictrader-api
cd automatictrader-api
python -m pytest
```

---

## 🤝 Collaboration Tips

### For External AI Agents (e.g., Jules from Google)

1. ✅ **Use test data** - All sample datasets are in repos
2. ✅ **Check feature branch** - Latest work is on `feature/v2-architecture` (traderunner)
3. ✅ **Run tests first** - Verify setup before changes
4. ✅ **Small commits** - Easier to review and merge
5. ✅ **Reference docs** - Org-Overview.md has full system context

### Merge Strategy

**Before merging your PR:**
1. Sync with base branch: `git pull origin feature/v2-architecture --rebase`
2. Run all tests: `pytest tests/`
3. Update documentation if needed
4. Request code review

---

## 🔧 Common Development Tasks

### Add a New Strategy (traderunner)
1. Create `src/strategies/your_strategy/`
2. Implement `BaseStrategy` interface
3. Add tests in `tests/test_your_strategy.py`
4. Test with sample data from `data/samples/`

### Add a New Market Data Provider (marketdata-stream)
1. Create `src/providers/your_provider.py`
2. Implement `MarketDataProvider` interface
3. Update `src/runner.py` to register provider
4. Test connection with `scripts/test_connection.py`

### Modify Order Logic (automatictrader-api)
1. Update `worker.py` or `storage.py`
2. Add unit tests
3. Test with paper trading mode first
4. Update API docs if endpoints changed

---

## 📞 Getting Help

- **Architecture questions:** See `Org-Overview.md`
- **Test data:** See `docs/TEST_DATA.md`
- **Strategy development:** See `docs/rudometkin_moc_strategy.md`
- **Paper trading:** See `docs/PAPER_TRADING_QUICKSTART.md`

---

## ⚡ TL;DR - Get Started in 60 Seconds

```bash
# 1. Clone main repo
git clone https://github.com/CyberForge275/traderunner.git
cd traderunner

# 2. Switch to development branch
git checkout feature/v2-architecture

# 3. Set up environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Verify with test data
python3 -c "import pandas as pd; print(pd.read_parquet('data/samples/rudometkin_test.parquet').head())"

# 5. Create your feature branch
git checkout -b feature/your-cool-feature

# 6. Start coding! 🚀
```

---

**GitHub Organization:** https://github.com/CyberForge275
**Repositories:**
- https://github.com/CyberForge275/traderunner
- https://github.com/CyberForge275/automatictrader-api
- https://github.com/CyberForge275/marketdata-stream

**Happy coding! 🎉**
