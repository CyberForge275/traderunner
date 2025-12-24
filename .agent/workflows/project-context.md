---
description: Project context and system knowledge for the droid-trading ecosystem
---

# droid-trading Project Context

> Reference this file at the start of any session to understand the full trading system architecture.

## System Overview

**Organization:** CyberForge275 on GitHub
**Architecture:** Microservices with 3 core components
**Owner:** Mirko

---

## Core Repositories

### 1. traderunner
- **Purpose:** Backtesting, research framework (Axiom-BT), signal generation
- **Local Path:** `/home/mirko/data/workspace/droid/traderunner`
- **GitHub:** https://github.com/CyberForge275/traderunner
- **Python:** 3.12
- **Key Commands:**
  ```bash
  # Activate virtual environment
  source .venv/bin/activate

  # Generate Inside Bar signals
  PYTHONPATH=src python -m signals.cli_inside_bar --help

  # Run dashboard
  streamlit run apps/dashboard.py
  ```
- **Active Strategies:** Inside Bar, Rudometkin MOC
- **Key Directories:**
  - `src/signals/` - Signal generators
  - `src/data/` - Data handling
  - `dashboard/` - Trading dashboard
  - `docs/` - Extensive documentation

### 2. automatictrader-api
- **Purpose:** Order intent pipeline, IB TWS integration, worker processing
- **Local Path:** `/home/mirko/data/workspace/automatictrader-api`
- **GitHub:** https://github.com/CyberForge275/automatictrader-api
- **Port:** 8080
- **Key Commands:**
  ```bash
  # API
  bash scripts/run_dev.sh

  # Worker (processes order intents)
  bash scripts/worker_dev.sh

  # Sanity check
  bash scripts/sanity.sh
  ```
- **API Endpoints:**
  - `POST /api/v1/orderintents` - Create order intent (requires Idempotency-Key header)
  - `GET /healthz` - Health check
- **Databases:**
  - `trading.db` - Order intents storage

### 3. marketdata-stream
- **Purpose:** Real-time market data via WebSocket (EODHD provider)
- **Local Path:** `/home/mirko/data/workspace/droid/marketdata-stream`
- **GitHub:** https://github.com/CyberForge275/marketdata-stream
- **Port:** 8090
- **Key Commands:**
  ```bash
  # Run service
  python -m src.runner

  # Health check
  curl http://localhost:8090/health
  ```
- **Key Features:**
  - Inside Bar pattern detection
  - Candle aggregation (M1, M5, M15)
  - Signal generation → `signals.db`
  - SQLite bridge to automatictrader-api

---

## Data Flow

```
EODHD WebSocket
       │
       ▼
marketdata-stream (port 8090)
   │   └── Inside Bar detection
   │   └── signals.db
   │
   ▼
sqlite_bridge.py ──────────────────────┐
                                       │
                                       ▼
automatictrader-api (port 8080)
   │   └── /api/v1/orderintents
   │   └── trading.db (order intents)
   │
   ▼
automatictrader-worker
   │   └── Polls pending intents
   │   └── Sends to IB TWS
   │
   ▼
Interactive Brokers (TWS/Gateway)
```

---

## Deployment

### Local Development
- All services run on localhost
- TWS runs on laptop (paper trading)

### Production (Debian Server)
- Systemd services for all components
- IB Gateway on separate process

---

## Key Documentation

| Document | Location |
|----------|----------|
| Org Overview | `traderunner/Org-Overview.md` |
| Paper Trading Setup | `traderunner/docs/PAPER_TRADING_QUICKSTART.md` |
| Inside Bar Live | `traderunner/docs/INSIDE_BAR_LIVE_TRADING.md` |
| Signal Generation | `traderunner/docs/AUTO_SIGNAL_GENERATION.md` |
| IB Worker Connection | `automatictrader-api/docs/WORKER_IB_CONNECTION.md` |

---

## Common Symbols
AAPL, MSFT, TSLA, NVDA, PLTR, HOOD, APP, META, GOOGL, AMZN

---

## Environment Files
- `.env` - Local configuration (gitignored)
- `.env.example` - Template with documentation
- `credentials.toml` - Secrets (gitignored)

---

## Current Focus (as of Dec 2024)
- Pre-PaperTrade simulation with Inside Bar strategy
- Automated signal generation during market hours
- Dashboard improvements and log monitoring
