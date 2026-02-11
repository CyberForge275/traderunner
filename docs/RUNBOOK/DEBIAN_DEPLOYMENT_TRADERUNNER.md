# Debian Deployment Runbook (Traderunner Ecosystem)

## 1. Purpose

This document is a deployment runbook for Debian servers for the current multi-repo setup:

- `traderunner`
- `marketdata-stream`
- `automatictrader-api`

It is evidence-based only. Values are filled only if they are explicitly present in repository documentation or service files. Unknown values are marked as `NOT_DEFINED_IN_REPO`.

## 2. Evidence Sources

Primary sources used:

- `docs/DEPLOYMENT_QUICK_START.md`
- `docs/MANUAL_DEPLOYMENT_STEPS.md`
- `docs/PRE_PAPERTRADE_SETUP.md`
- `docs/PAPER_TRADING_CHECKLIST.md`
- `docs/TESTING_AND_DEPLOYMENT.md`
- `docs/FIX_EODHD_CONNECTION.md`
- `trading_dashboard/systemd/trading-dashboard-v2.service`
- `AGENTS.md`

## 3. Target System (Fact Sheet)

### 3.1 Infrastructure

| Field | Value | Evidence |
|---|---|---|
| `SERVER_HOST` | `192.168.178.55` | `docs/DEPLOYMENT_QUICK_START.md`, `docs/PRE_PAPERTRADE_SETUP.md` |
| `SSH_USER` | `mirko` | `docs/MANUAL_DEPLOYMENT_STEPS.md`, `docs/FIX_EODHD_CONNECTION.md` |
| `SSH_PORT` | `22` | inferred from all `ssh` examples without `-p`; no override documented |
| `SERVER_ENV` | `NOT_DEFINED_IN_REPO` | no explicit staging/prod split found |

### 3.2 Base Paths

| Field | Value | Evidence |
|---|---|---|
| `BASE_DIR` | `/opt/trading` | `docs/TESTING_AND_DEPLOYMENT.md` (`SERVER_DIR="/opt/trading"`) |
| `TRADERUNNER_DIR` | `/opt/trading/traderunner` | multiple deployment docs |
| `MARKETDATA_DIR` | `/opt/trading/marketdata-stream` | multiple deployment docs |
| `AUTOMATICTRADER_DIR` | `/opt/trading/automatictrader-api` | multiple deployment docs |

## 4. Services That Must Run

### 4.1 Core Services

| Service | Required For | Evidence |
|---|---|---|
| `marketdata-stream` | live ticks + signal generation | `docs/PRE_PAPERTRADE_SETUP.md`, `docs/PAPER_TRADING_CHECKLIST.md` |
| `automatictrader-api` | order intent API | `docs/PAPER_TRADING_CHECKLIST.md`, `docs/TESTING_AND_DEPLOYMENT.md` |
| `automatictrader-worker` | intent processing / paper send | `docs/PAPER_TRADING_CHECKLIST.md`, `docs/TESTING_AND_DEPLOYMENT.md` |
| `trading-dashboard-v2` | dashboard UI | `AGENTS.md`, `trading_dashboard/systemd/trading-dashboard-v2.service` |

### 4.2 Optional Service

| Service | Purpose | Evidence |
|---|---|---|
| `ibgateway` | headless IB Gateway | `docs/IB_GATEWAY_HEADLESS.md` |

## 5. Port and Healthcheck Matrix

| Component | Port | Health Endpoint | Evidence |
|---|---|---|---|
| `marketdata-stream` | `8090/tcp` | `http://localhost:8090/health` | `docs/FIX_EODHD_CONNECTION.md` |
| `automatictrader-api` | `8080/tcp` | `http://localhost:8080/healthz` | `docs/TESTING_AND_DEPLOYMENT.md`, `docs/PAPER_TRADING_CHECKLIST.md` |
| `trading-dashboard-v2` | `9001/tcp` | `NOT_DEFINED_IN_REPO` | `trading_dashboard/systemd/trading-dashboard-v2.service` |

Notes:
- Some older docs still mention `marketdata-stream` on port `8000`; current fix doc marks `8090` as correct.

## 6. Runtime User/Group

| Service | User | Group | Evidence |
|---|---|---|---|
| `automatictrader-api` | `trading` (example systemd) | `trading` | `docs/TESTING_AND_DEPLOYMENT.md` |
| `automatictrader-worker` | `trading` (example systemd) | `trading` | `docs/TESTING_AND_DEPLOYMENT.md` |
| `trading-dashboard-v2` | `mirko` | `mirko` | `trading_dashboard/systemd/trading-dashboard-v2.service` |
| `marketdata-stream` | `NOT_DEFINED_IN_REPO` | `NOT_DEFINED_IN_REPO` | no unit file in this repo |

## 7. Environment Files and Variables

### 7.1 Environment File Locations

| Component | Env file path | Evidence |
|---|---|---|
| `marketdata-stream` | `/opt/trading/marketdata-stream/.env` | `docs/PRE_PAPERTRADE_SETUP.md` |
| `automatictrader-api` | `/opt/trading/automatictrader-api/.env` | `docs/TESTING_AND_DEPLOYMENT.md` |
| `trading-dashboard-v2` | no separate file in unit (inline `Environment=`) | `trading_dashboard/systemd/trading-dashboard-v2.service` |

### 7.2 Required/Operational Variables

#### marketdata-stream

| Variable | Example/Expected | Evidence |
|---|---|---|
| `EODHD_API_KEY` | `demo` or real key | `docs/FIX_EODHD_CONNECTION.md` |
| `EODHD_ENDPOINT` | `us` | `docs/FIX_EODHD_CONNECTION.md` |
| `WATCH_SYMBOLS` | `HOOD,PLTR,...` | `docs/FIX_EODHD_CONNECTION.md` |
| `SIGNALS_DB_PATH` | `/opt/trading/marketdata-stream/data/signals.db` | `docs/prepaper/CLI_LIVE_SMOKE_RUNBOOK.md` |
| `MARKETDATA_PROVIDER` | `real` (in smoke runbook context) | `docs/prepaper/CLI_LIVE_SMOKE_RUNBOOK.md` |

#### automatictrader-api / worker

| Variable | Example/Expected | Evidence |
|---|---|---|
| `AT_BIND_HOST` | `127.0.0.1` | `docs/TESTING_AND_DEPLOYMENT.md` |
| `AT_BIND_PORT` | `8080` | `docs/TESTING_AND_DEPLOYMENT.md` |
| `AT_DB_PATH` | `/opt/trading/automatictrader-api/data/automatictrader.db` | `docs/TESTING_AND_DEPLOYMENT.md` |
| `AT_WORKER_MODE` | `plan-only` or `paper-send` | `docs/TESTING_AND_DEPLOYMENT.md`, `docs/PAPER_TRADING_CHECKLIST.md` |
| `AT_IB_HOST` | e.g. `127.0.0.1` | `docs/PAPER_TRADING_QUICKSTART.md` |
| `AT_IB_PORT` | `4002` (paper) | `docs/PAPER_TRADING_QUICKSTART.md` |

#### traderunner / dashboard related

| Variable | Example/Expected | Evidence |
|---|---|---|
| `PYTHONPATH` | `/opt/trading/traderunner` or `src:.` in local runs | dashboard unit + docs |
| `DASHBOARD_PORT` | `9001` | `trading_dashboard/systemd/trading-dashboard-v2.service` |
| `DASHBOARD_USER` | `admin` | `trading_dashboard/systemd/trading-dashboard-v2.service` |
| `DASHBOARD_PASS` | `admin` | `trading_dashboard/systemd/trading-dashboard-v2.service` |
| `AXIOM_BT_PORTFOLIO_REPORT` | `1` (feature flag) | `docs/PORTFOLIO_HARDENING_STATUS.md` |
| `USE_LEGACY_PIPELINE` | used in run/start commands | command history in repo docs/instructions |
| `DASH_UI_DEBUG` | optional debug mode | `AGENTS.md` |

## 8. Systemd: Known Unit Definitions

### 8.1 automatictrader-api

Expected unit path:

- `/etc/systemd/system/automatictrader-api.service`

Documented essentials:

- `WorkingDirectory=/opt/trading/automatictrader-api`
- `EnvironmentFile=/opt/trading/automatictrader-api/.env`
- `ExecStart=/opt/trading/automatictrader-api/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8080`

Source: `docs/TESTING_AND_DEPLOYMENT.md`

### 8.2 automatictrader-worker

Expected unit path:

- `/etc/systemd/system/automatictrader-worker.service`

Documented essentials:

- `After=network.target automatictrader-api.service`
- `Requires=automatictrader-api.service`
- `WorkingDirectory=/opt/trading/automatictrader-api`
- `EnvironmentFile=/opt/trading/automatictrader-api/.env`
- `ExecStart=/opt/trading/automatictrader-api/.venv/bin/python worker.py`

Source: `docs/TESTING_AND_DEPLOYMENT.md`

### 8.3 trading-dashboard-v2

Unit file exists in repo:

- `trading_dashboard/systemd/trading-dashboard-v2.service`

Documented essentials:

- `WorkingDirectory=/opt/trading/traderunner`
- `Environment=MARKETDATA_DIR=/opt/trading/marketdata-stream`
- `Environment=AUTOMATICTRADER_DIR=/opt/trading/automatictrader-api`
- `Environment=PYTHONPATH=/opt/trading/traderunner`
- `Environment=DASHBOARD_PORT=9001`
- `ExecStart=... gunicorn ... trading_dashboard.app:server`

### 8.4 marketdata-stream

Service name is documented, but full unit file content is not available in this repository.

## 9. Deployment Procedure (Debian)

### 9.1 Precheck

1. SSH access to server:
   - `ssh mirko@192.168.178.55`
2. Confirm directories exist:
   - `/opt/trading/traderunner`
   - `/opt/trading/marketdata-stream`
   - `/opt/trading/automatictrader-api`
3. Confirm `.env` files exist:
   - `/opt/trading/marketdata-stream/.env`
   - `/opt/trading/automatictrader-api/.env`

### 9.2 Service Startup Order

1. `marketdata-stream`
2. `automatictrader-api`
3. `automatictrader-worker`
4. `trading-dashboard-v2` (if dashboard needed)

### 9.3 Health Validation

1. `curl http://localhost:8090/health`
2. `curl http://localhost:8080/healthz`
3. `sudo systemctl status marketdata-stream`
4. `sudo systemctl status automatictrader-api`
5. `sudo systemctl status automatictrader-worker`
6. `sudo systemctl status trading-dashboard-v2`

### 9.4 Logs

- `sudo journalctl -u marketdata-stream -f`
- `sudo journalctl -u automatictrader-api -f`
- `sudo journalctl -u automatictrader-worker -f`
- `sudo journalctl -u trading-dashboard-v2 -f`

## 10. Security/Operations Gaps (Missing in Current Repo)

The following deployment-critical values are not hard-defined in current repo docs and must be decided by Deployment Manager before production rollout:

- explicit `staging` vs `prod` environment model
- canonical `ETC_DIR` (e.g. `/etc/<app>`) for all services
- canonical `LOG_DIR` if not using journal-only policy
- single release manifest repository and lock file (`repos.lock`) with pinned SHAs
- artifact naming/signing policy (`TAG`, `ARTIFACT_NAME`, `ARTIFACT_SHA256`, retention)
- dedicated non-personal service account standardization (`mirko` vs `trading`)

## 11. Filled Template (Evidence-Only)

### Zielsystem

- `<SERVER_HOST>`: `192.168.178.55`
- `<SSH_USER>`: `mirko`
- `<SSH_PORT>`: `22`
- `<SERVER_ENV>`: `NOT_DEFINED_IN_REPO`

### App/Service

- `<APP_NAME>`: `NOT_DEFINED_IN_REPO`
- `<SERVICE_NAME>`: `marketdata-stream`, `automatictrader-api`, `automatictrader-worker`, `trading-dashboard-v2`
- `<SERVICE_USER>`: `trading` (API/worker examples), `mirko` (dashboard unit)
- `<SERVICE_GROUP>`: `trading` (API/worker examples), `mirko` (dashboard unit)
- `<BASE_DIR>`: `/opt/trading`
- `<ETC_DIR>`: `NOT_DEFINED_IN_REPO`
- `<LOG_DIR>`: `NOT_DEFINED_IN_REPO`
- `<DATA_DIR>`: `/opt/trading/automatictrader-api/data`, `/opt/trading/marketdata-stream/data`
- `<PYTHON_BIN>`: `python3` (venv-based; no single fixed absolute path mandated)
- `<APP_ENTRYPOINT_MODULE>`:
  - API: `app:app` via `uvicorn`
  - Worker: `worker.py`
- `<HEALTHCHECK_URL>`:
  - `http://localhost:8090/health`
  - `http://localhost:8080/healthz`
- `<HEALTHCHECK_MODULE>`: `NOT_DEFINED_IN_REPO`
- `<PORTS>`: `8090/tcp`, `8080/tcp`, `9001/tcp`

### Multi-Repo

- `<RELEASE_MANIFEST_REPO>`: `NOT_DEFINED_IN_REPO`
- `<REPOS_LOCK_PATH>`: `NOT_DEFINED_IN_REPO`
- `<REPOS>`: `traderunner`, `marketdata-stream`, `automatictrader-api`

### Config/Secrets

- `<ENV_FILE_PATH>`:
  - `/opt/trading/marketdata-stream/.env`
  - `/opt/trading/automatictrader-api/.env`
- `<SECRETS_PATH>`: `NOT_DEFINED_IN_REPO`

### Release

- `<TAG>`: `NOT_DEFINED_IN_REPO`
- `<ARTIFACT_NAME>`: `NOT_DEFINED_IN_REPO`
- `<ARTIFACT_SHA256>`: `NOT_DEFINED_IN_REPO`
- `<KEEP_RELEASES>`: `NOT_DEFINED_IN_REPO`

## 12. Recommended Missing Additions (to close operational gaps)

1. Add a canonical infra release manifest file (e.g. `repos.lock`) with repo URLs + commit SHAs.
2. Add systemd unit file for `marketdata-stream` to this repository.
3. Standardize service users/groups across all units.
4. Add a single Debian production runbook with staging/prod split and secret handling policy.
5. Add backup/restore procedures for:
   - `/opt/trading/marketdata-stream/data/signals.db`
   - `/opt/trading/automatictrader-api/data/automatictrader.db`
   - `/opt/trading/traderunner/artifacts/backtests`

