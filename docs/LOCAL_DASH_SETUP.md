# Local Dash Dashboard Setup

This guide documents the "well known shortcut" and procedures for starting the Trading Dashboard on localhost.

## Quick Start (Shortcut)

To start the server with all dependencies and correct pathing, run the following from the repository root:

```bash
cd /home/mirko/data/workspace/droid/traderunner
. .venv/bin/activate

PYTHONNOUSERSITE=1 \
PYTHONPATH="$(pwd):$(pwd)/src" \
HOST=127.0.0.1 \
PORT=9001 \
python trading_dashboard/app.py
```

## Verification

### 1. Check if the port is listening
```bash
ss -ltnp | grep 9001
```

### 2. Verify HTTP response
```bash
curl -Is http://127.0.0.1:9001 | head
```
*Note: Expect a `401 UNAUTHORIZED` response due to Basic Auth.*

## Access Credentials
- **URL**: [http://localhost:9001](http://localhost:9001)
- **Username**: `admin`
- **Password**: `admin`

## Troubleshooting
- **Port Conflict**: If 9001 is in use, kill the existing process: `lsof -ti:9001 | xargs kill -9`.
- **Logs**: Startup logs are typically directed to `/tmp/dashboard_startup.log` during ad-hoc runs or found in `logs/dashboard.log` for persisted runs.
- **Dependencies**: Ensure the virtual environment is active and `trading_dashboard/requirements.txt` is installed.

---
*Maintained by: Antigravity*
*Last updated: 2026-01-12*
