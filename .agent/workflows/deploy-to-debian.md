---
description: Deploy trading system to Debian server (192.168.178.55)
---

# Deploy to Debian Server

> One-click deployment of the Automatic Trading Factory to the Debian test server.

## Prerequisites
- SSH access to `mirko@192.168.178.55`
- Services already installed on server
- TWS/IB Gateway running if needed for worker

---

## Quick Deploy (Ansible - Recommended)

// turbo-all

1. Navigate to deployment directory:
```bash
cd /home/mirko/data/workspace/droid/marketdata-stream/deployment
```

2. Run health check first:
```bash
ansible-playbook playbooks/health_check.yml -i inventory/test.yml
```

3. Deploy all services:
```bash
ansible-playbook playbooks/deploy.yml -i inventory/test.yml
```

4. Verify deployment:
```bash
curl http://192.168.178.55:8080/healthz && curl http://192.168.178.55:8090/health
```

---

## Manual Deploy (Fallback)

// turbo-all

1. SSH to server:
```bash
ssh mirko@192.168.178.55
```

2. Pull latest code for each service:
```bash
cd /opt/trading/marketdata-stream && git pull origin main
cd /opt/trading/automatictrader-api && git pull origin main
cd /opt/trading/traderunner && git pull origin feature/v2-architecture
```

3. Install any new dependencies:
```bash
cd /opt/trading/marketdata-stream && source .venv/bin/activate && pip install -r requirements.txt
cd /opt/trading/automatictrader-api && source .venv/bin/activate && pip install -r requirements.txt
```

4. Restart all services:
```bash
sudo systemctl restart marketdata-stream signal-processor automatictrader-api automatictrader-worker
```

5. Verify services:
```bash
sudo systemctl status marketdata-stream automatictrader-api automatictrader-worker --no-pager
```

6. Check health endpoints:
```bash
curl http://localhost:8080/healthz
curl http://localhost:8090/health
```

---

## Deploy Single Service

### marketdata-stream only:
```bash
ansible-playbook playbooks/deploy.yml -i inventory/test.yml --tags marketdata-stream
```

### automatictrader-api only:
```bash
ansible-playbook playbooks/deploy.yml -i inventory/test.yml --tags automatictrader-api
```

---

## Rollback

If deployment fails:
```bash
ansible-playbook playbooks/rollback.yml -i inventory/test.yml
# Enter backup timestamp when prompted (or 'latest')
```

---

## Monitoring After Deploy

| Dashboard | URL |
|-----------|-----|
| Trading Status | http://192.168.178.55:9000 |
| Grafana | http://192.168.178.55:3000 |
| API Health | http://192.168.178.55:8080/healthz |
| MD Health | http://192.168.178.55:8090/health |

---

## Troubleshooting

### Service won't start
```bash
sudo journalctl -u marketdata-stream -n 50 --no-pager
sudo journalctl -u automatictrader-api -n 50 --no-pager
```

### Check logs
```bash
tail -f /opt/trading/marketdata-stream/marketdata.log
tail -f /opt/trading/automatictrader-api/api.log
```
