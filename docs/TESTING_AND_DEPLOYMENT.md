# Testing the Paper Trading Adapter

## Local Testing (Development Machine)

### Step 1: Start automatictrader-api

```bash
# Terminal 1
cd /home/mirko/data/workspace/automatictrader-api
source .venv/bin/activate  # or: . .venv/bin/activate
bash scripts/run_dev.sh
```

Expected output:
```
INFO:     Started server process
INFO:     Uvicorn running on http://127.0.0.1:8080
```

### Step 2: Start the Worker

```bash
# Terminal 2
cd /home/mirko/data/workspace/automatictrader-api
source .venv/bin/activate
bash scripts/worker_dev.sh
```

Expected output:
```
INFO automatictrader-worker - worker running, db=./data/automatictrader.db, mode=plan-only
```

### Step 3: Generate Test Signals

```bash
# Terminal 3
cd /home/mirko/data/workspace/droid/traderunner
PYTHONPATH=src python -m signals.cli_rudometkin_moc \
  --symbols AAPL,MSFT \
  --start 2025-11-20 \
  --end 2025-11-22 \
  --output artifacts/signals/test_signals.csv

# Verify signals were created
cat artifacts/signals/test_signals.csv
```

### Step 4: Test Health Check

```bash
cd /home/mirko/data/workspace/droid/traderunner
PYTHONPATH=src python -m trade.paper_trading_adapter \
  --signals artifacts/signals/test_signals.csv \
  --health-check-only
```

Expected output:
```
✓ API health check passed
```

### Step 5: Send Signals to API

```bash
PYTHONPATH=src python -m trade.paper_trading_adapter \
  --signals artifacts/signals/test_signals.csv \
  --api-url http://localhost:8080
```

Expected output:
```
INFO paper_trading_adapter - ✓ API health check passed
INFO paper_trading_adapter - Intent created: id=1 symbol=AAPL side=LONG qty=10
INFO paper_trading_adapter - Intent created: id=2 symbol=MSFT side=LONG qty=5
============================================================
SUMMARY:
  Total signals:     2
  Created intents:   2
  Duplicates:        0
  Skipped:           0
  Errors:            0
============================================================
```

### Step 6: Verify in Database

```bash
cd /home/mirko/data/workspace/automatictrader-api
sqlite3 data/automatictrader.db << EOF
SELECT id, symbol, side, quantity, status, created_at 
FROM order_intents 
ORDER BY id DESC 
LIMIT 10;
EOF
```

Or use the API:
```bash
curl http://localhost:8080/intents?limit=10 | python -m json.tool
```

### Step 7: Test Idempotency

Send the same signals again:
```bash
cd /home/mirko/data/workspace/droid/traderunner
PYTHONPATH=src python -m trade.paper_trading_adapter \
  --signals artifacts/signals/test_signals.csv \
  --api-url http://localhost:8080
```

Expected output:
```
SUMMARY:
  Total signals:     2
  Created intents:   0
  Duplicates:        2    ← Idempotency working!
  Skipped:           0
  Errors:            0
```

---

## Automated Testing

Run the test suite:
```bash
cd /home/mirko/data/workspace/droid/traderunner
PYTHONPATH=src python -m pytest tests/test_paper_trading_adapter.py -v
```

Expected: 14-15 tests passing

---

## Deployment to Debian Server

### Prerequisites

- Debian/Ubuntu server with SSH access
- Python 3.9+ installed
- sudo access for systemd setup

### Option 1: Manual Deployment (Quick)

#### 1. Copy Projects to Server

```bash
# From your local machine
SERVER="user@your-debian-server.com"
SERVER_DIR="/opt/trading"

# Create remote directory
ssh $SERVER "sudo mkdir -p $SERVER_DIR && sudo chown $USER:$USER $SERVER_DIR"

# Copy traderunner
rsync -avz --exclude '.git' --exclude '__pycache__' --exclude 'artifacts' \
  /home/mirko/data/workspace/droid/traderunner/ \
  $SERVER:$SERVER_DIR/traderunner/

# Copy automatictrader-api
rsync -avz --exclude '.git' --exclude '__pycache__' --exclude 'data' \
  /home/mirko/data/workspace/automatictrader-api/ \
  $SERVER:$SERVER_DIR/automatictrader-api/
```

#### 2. Setup on Server

```bash
# SSH into server
ssh $SERVER

# Setup automatictrader-api
cd /opt/trading/automatictrader-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Setup traderunner
cd /opt/trading/traderunner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create necessary directories
mkdir -p data artifacts/signals artifacts/orders
```

#### 3. Configure Environment

```bash
cd /opt/trading/automatictrader-api
cp .env.example .env
nano .env
```

Edit `.env`:
```env
AT_BIND_HOST=127.0.0.1
AT_BIND_PORT=8080
AT_DB_PATH=/opt/trading/automatictrader-api/data/automatictrader.db
AT_WORKER_MODE=plan-only  # Start with plan-only
AT_WORKER_POLL_SEC=1.0
```

#### 4. Test on Server

```bash
# Terminal 1: Start API
cd /opt/trading/automatictrader-api
source .venv/bin/activate
python -m uvicorn app:app --host 127.0.0.1 --port 8080

# Terminal 2: Test adapter
cd /opt/trading/traderunner
source .venv/bin/activate
PYTHONPATH=src python -m trade.paper_trading_adapter \
  --signals artifacts/signals/test_signals.csv \
  --health-check-only
```

### Option 2: Systemd Services (Production)

#### 1. Create Service Files

**API Service**: `/etc/systemd/system/automatictrader-api.service`
```ini
[Unit]
Description=Automatic Trader API
After=network.target

[Service]
Type=simple
User=trading  # Create dedicated user for security
WorkingDirectory=/opt/trading/automatictrader-api
Environment="PATH=/opt/trading/automatictrader-api/.venv/bin"
EnvironmentFile=/opt/trading/automatictrader-api/.env
ExecStart=/opt/trading/automatictrader-api/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Worker Service**: `/etc/systemd/system/automatictrader-worker.service`
```ini
[Unit]
Description=Automatic Trader Worker
After=network.target automatictrader-api.service
Requires=automatictrader-api.service

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/trading/automatictrader-api
Environment="PATH=/opt/trading/automatictrader-api/.venv/bin"
EnvironmentFile=/opt/trading/automatictrader-api/.env
ExecStart=/opt/trading/automatictrader-api/.venv/bin/python worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 2. Enable and Start Services

```bash
# Create trading user
sudo useradd -r -s /bin/bash -d /opt/trading trading
sudo chown -R trading:trading /opt/trading

# Install services
sudo systemctl daemon-reload
sudo systemctl enable automatictrader-api
sudo systemctl enable automatictrader-worker

# Start services
sudo systemctl start automatictrader-api
sudo systemctl start automatictrader-worker

# Check status
sudo systemctl status automatictrader-api
sudo systemctl status automatictrader-worker
```

#### 3. Monitor Logs

```bash
# API logs
sudo journalctl -u automatictrader-api -f

# Worker logs
sudo journalctl -u automatictrader-worker -f
```

### Option 3: Docker Deployment (Advanced)

Create `Dockerfile` for traderunner:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY artifacts/ ./artifacts/

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "trade.paper_trading_adapter", "--help"]
```

Build and run:
```bash
docker build -t traderunner-adapter .
docker run -v $(pwd)/artifacts:/app/artifacts traderunner-adapter \
  python -m trade.paper_trading_adapter \
  --signals /app/artifacts/signals/test_signals.csv \
  --api-url http://host.docker.internal:8080
```

---

## Security Considerations for Production

### 1. API Authentication

Enable bearer token in `automatictrader-api/.env`:
```env
AT_BEARER_TOKEN=your-secure-random-token-here
```

Use in adapter:
```bash
PYTHONPATH=src python -m trade.paper_trading_adapter \
  --signals signals.csv \
  --bearer-token your-secure-random-token-here
```

### 2. Firewall Rules

```bash
# Only allow localhost connections to API
sudo ufw allow from 127.0.0.1 to any port 8080
sudo ufw deny 8080
```

### 3. File Permissions

```bash
# Restrict access to trading directory
sudo chmod 750 /opt/trading
sudo chown -R trading:trading /opt/trading

# Protect .env file
chmod 600 /opt/trading/automatictrader-api/.env
```

### 4. Monitoring

Set up monitoring with:
- Log rotation: `/etc/logrotate.d/trading`
- Health checks: Cron job pinging `/healthz`
- Alerts: Email/SMS on service failure

---

## Troubleshooting

### API Not Starting
```bash
# Check if port is already in use
sudo lsof -i :8080

# Check logs
sudo journalctl -u automatictrader-api -n 50
```

### Adapter Can't Connect
```bash
# Test API directly
curl http://localhost:8080/healthz

# Check firewall
sudo ufw status
```

### Permission Errors
```bash
# Fix ownership
sudo chown -R trading:trading /opt/trading

# Fix Python path
which python  # Should be in .venv/bin/python
```

### Database Lock Errors
```bash
# Check if multiple workers are running
ps aux | grep worker.py

# Restart services
sudo systemctl restart automatictrader-worker
```

---

## Next Steps After Deployment

1. **Monitor for 24 hours** with `plan-only` mode
2. **Verify intents** are being created correctly
3. **Enable IB integration** (set `AT_WORKER_MODE=paper-send`)
4. **Add scheduling** for automated signal generation
5. **Set up monitoring dashboard**
