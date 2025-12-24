# droid-trading – System Overview

Central documentation for the droid-trading ecosystem across multiple repositories.

---

## Repositories

### **traderunner**
Backtesting and research framework (Axiom-BT).
**Focus:** Strategies, data contracts, replay engine, dashboards.
**Repository:** https://github.com/CyberForge275/traderunner
**Local Path:** `/home/mirko/data/workspace/droid/traderunner`
**Status:** ✅ Active on GitHub

### **automatictrader-api**
API + Worker that processes signals into order intents and sends them to Interactive Brokers (TWS).
**Focus:** Planning, idempotency, risk limits, health checks.
**Previous Repository:** https://dev.azure.com/mirko2175/AutomaticTrader/_git/AutomaticTrader _(archived)_
**Repository:** https://github.com/CyberForge275/automatictrader-api
**Local Path:** `/home/mirko/data/workspace/automatictrader-api`
**Status:** ✅ Migrated to GitHub

### **marketdata-stream**
Provider-agnostic market data service with WebSocket connectivity.
**Focus:** Real-time data from EODHD (and later other providers) streamed/stored in internal format.
**Repository:** https://github.com/CyberForge275/marketdata-stream
**Local Path:** `/home/mirko/data/workspace/droid/marketdata-stream`
**Status:** ✅ Active on GitHub

### **deployment** _(optional)_
Shared infrastructure artifacts: Docker Compose, K8s manifests, systemd templates, runbooks.
**Repository:** https://github.com/CyberForge275/deployment _(future)_
**Status:** 📋 Planned

---

## System Architecture

```
┌─────────────────────┐
│ marketdata-stream   │  WebSocket → EODHD/other providers
│                     │  Exposes: REST API, WebSocket, Files
└──────────┬──────────┘
           │
           ├──────────────────┐
           │                  │
           ▼                  ▼
┌─────────────────┐  ┌────────────────────┐
│  traderunner    │  │ Other Strategies   │
│  (Research/BT)  │  │ (Live/Paper)       │
└────────┬────────┘  └─────────┬──────────┘
         │                     │
         │  Signals/Orders     │
         └──────────┬──────────┘
                    ▼
        ┌───────────────────────┐
        │ automatictrader-api   │
        │ Order Intent Pipeline │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Interactive Brokers   │
        │ TWS/Gateway           │
        └───────────────────────┘
```

---

## Data Flow

### **1. marketdata-stream**
→ Fetches real-time data (WebSocket) from EODHD or other providers
→ Provides data internally (REST API, WebSocket, files, DB, queue)

### **2. traderunner**
→ Uses historical data (Daily + Intraday) for research and backtesting
→ Delivers standardized output artifacts (Signals, Orders, Backtest Metrics)

### **3. automatictrader-api**
→ Processes signals/orders (from traderunner or external strategies)
→ Plans and sends orders to IBKR (TWS), with idempotency and safety gates

---

## Design Principles

This multi-repo architecture enables:

- **Independent versioning and deployments** - Each service evolves at its own pace
- **Clear responsibilities** - Each repo has a single, well-defined purpose
- **Selective open-sourcing** - Can open traderunner without exposing live trading secrets
- **Technology flexibility** - Each service can use optimal tech stack
- **Team scalability** - Different teams can own different services
- **Security boundaries** - Sensitive trading logic separated from public research tools

---

## Communication Patterns

### **marketdata-stream → traderunner**
- **During research:** Historical data files (Parquet/CSV)
- **During live:** REST API or WebSocket for real-time ticks/candles

### **traderunner → automatictrader-api**
- **Method:** HTTP POST to `/api/v1/orderintents`
- **Format:** JSON with idempotency key
- **Contract:** SignalOutputSpec validation

### **automatictrader-api → IB TWS**
- **Method:** `ib_insync` library
- **Protocol:** TWS API
- **Modes:** Plan-only, Paper-send, Live-send

---

## Deployment Topology

### **Development (Local)**
```bash
# Terminal 1: Market Data
cd /home/mirko/data/workspace/droid/marketdata-stream && python -m src.runner

# Terminal 2: Order API
cd /home/mirko/data/workspace/automatictrader-api && python -m app

# Terminal 3: Worker
cd /home/mirko/data/workspace/automatictrader-api && python -m worker

# Terminal 4: Strategy
cd /home/mirko/data/workspace/droid/traderunner && streamlit run apps/dashboard.py
```

### **Production (Debian Server)**
```
Systemd Services:
├── marketdata-stream.service
├── automatictrader-api.service
└── automatictrader-worker.service

IB TWS/Gateway: Separate VM or Docker container
```

### **Docker Compose (Alternative)**
```yaml
services:
  marketdata-stream:
    image: marketdata-stream:latest
    ports: ["8090:8090"]

  automatictrader-api:
    image: automatictrader-api:latest
    ports: ["8080:8080"]

  automatictrader-worker:
    image: automatictrader-api:latest
    command: python -m worker
```

---

## Repository Management Strategy

### **GitHub Organization Structure**

**Current:** All repositories under `CyberForge275` GitHub account

```
github.com/CyberForge275/
├── traderunner           → Research & backtesting (public)
├── automatictrader-api   → Order execution (private)
├── marketdata-stream     → Data streaming (private)
└── deployment           → Infrastructure (planned, private)
```

### **Visibility Recommendations**

| Repository | Visibility | Reason |
|------------|-----------|---------|
| **traderunner** | Public | Research framework, no trading secrets |
| **automatictrader-api** | Private | Contains order logic and broker integration |
| **marketdata-stream** | Private/Public | Consider public to help community |
| **deployment** | Private | Contains infrastructure secrets |

### **Branch Protection**

For all repositories, enable:
- [x] Require pull request reviews before merging
- [x] Require status checks to pass before merging
- [x] Require branches to be up to date before merging
- [x] Include administrators in restrictions

---

## Quick Links

### Repositories
- [traderunner](https://github.com/CyberForge275/traderunner)
- [automatictrader-api](https://github.com/CyberForge275/automatictrader-api)
- [marketdata-stream](https://github.com/CyberForge275/marketdata-stream)
- [automatictrader-api (Azure DevOps - archived)](https://dev.azure.com/mirko2175/AutomaticTrader/_git/AutomaticTrader)

### Documentation
- [traderunner README](./README.md)
- [automatictrader-api README](/home/mirko/data/workspace/automatictrader-api/README.md)
- [marketdata-stream README](/home/mirko/data/workspace/droid/marketdata-stream/README.md)
- [marketdata-stream OVERVIEW](/home/mirko/data/workspace/droid/marketdata-stream/OVERVIEW.md)

### Migration Guides
- [Azure DevOps to GitHub Migration Guide](/home/mirko/data/workspace/automatictrader-api/GITHUB_MIGRATION_GUIDE.md)

---

## Version History

- **v1.0** (2024-11-27) - Initial multi-repo architecture defined
- **v0.2** (2024-11-27) - marketdata-stream refactored to provider-based architecture
- **v1.1** (2024-11-28) - Centralized organization overview created

---

**Maintained by:** droid-trading team
**Last updated:** 2024-11-28
**Local workspace:** `/home/mirko/data/workspace/droid/`
