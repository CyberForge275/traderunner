# Monitoring Stack Deployment Guide - Debian Server

## Prerequisites

Ensure your Debian server has:
- Docker Engine installed
- Docker Compose installed
- Ports available: 9090 (Prometheus), 3000 (Grafana), 9093 (Alertmanager)
- ~500MB free RAM
- Trading services running (automatictrader-api on :8080)

## Quick Deployment

### 1. Copy Monitoring Configuration to Server

```bash
# From your local machine
cd /home/mirko/data/workspace/droid/traderunner

# Copy monitoring directory to Debian server
scp -r monitoring/ user@debian-server:/opt/trading/traderunner/
```

### 2. SSH to Server and Start Stack

```bash
ssh user@debian-server

cd /opt/trading/traderunner/monitoring

# Start monitoring stack
docker-compose up -d

# Verify services started
docker-compose ps
```

Expected output:
```
NAME                   STATUS    PORTS
trading-prometheus     Up        0.0.0.0:9090->9090/tcp
trading-grafana        Up        0.0.0.0:3000->3000/tcp
trading-alertmanager   Up        0.0.0.0:9093->9093/tcp
```

### 3. Verify Health

```bash
# Check Prometheus
curl http://localhost:9090/-/healthy
# Expected: Prometheus is Healthy.

# Check Grafana
curl http://localhost:3000/api/health
# Expected: {"commit":"...","database":"ok","version":"..."}

# Check Alertmanager
curl http://localhost:9093/-/healthy
# Expected: OK
```

### 4. Verify Metrics Collection

```bash
# Check if Prometheus is scraping automatictrader-api
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="automatictrader-api")'
```

Expected: `"health": "up"`

---

## Access Dashboards from Your Laptop

### Option 1: SSH Tunnel (Recommended for Security)

```bash
# From your laptop
ssh -L 3000:localhost:3000 -L 9090:localhost:9090 user@debian-server

# Keep this terminal open
# Open browser to:
# - Grafana: http://localhost:3000
# - Prometheus: http://localhost:9090
```

### Option 2: Direct Access (if firewall allows)

```bash
# On Debian server, allow ports (UFW example)
sudo ufw allow 3000/tcp  # Grafana
sudo ufw allow 9090/tcp  # Prometheus

# Access from browser:
http://debian-server-ip:3000  # Grafana
http://debian-server-ip:9090  # Prometheus
```

⚠️ **Security Warning**: Only use Option 2 on a trusted network. For internet access, use SSH tunnel or reverse proxy with HTTPS.

---

## First-Time Grafana Setup

### 1. Login

**URL**: http://localhost:3000
**Default credentials**: `admin` / `admin`

You'll be prompted to change the password on first login.

### 2. Verify Prometheus Data Source

1. Click **Configuration** (gear icon) → **Data Sources**
2. You should see **Prometheus** already configured
3. Click **Test** button → should show "Data source is working"

If not configured:
- Click **Add data source**
- Select **Prometheus**
- URL: `http://prometheus:9090`
- Click **Save & Test**

### 3. Import Dashboards

**Method 1: Using Dashboard JSONs**

1. Click **+** (Create) → **Import**
2. Click **Upload JSON file**
3. Select dashboard file from `/var/lib/grafana/dashboards/`
4. Click **Load**
5. Select **Prometheus** as data source
6. Click **Import**

**Method 2: From Grafana.com**

1. Click **+** → **Import**
2. Enter dashboard ID:
   - `1860` - Node Exporter Full
   - `3662` - Prometheus 2.0 Stats
3. Click **Load** → **Import**

---

## Monitoring Stack Management

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f prometheus
docker-compose logs -f grafana
docker-compose logs -f alertmanager
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart grafana
```

### Stop Stack

```bash
# Stop (keeps data)
docker-compose stop

# Stop and remove containers (keeps data volumes)
docker-compose down

# Stop and remove everything including data (CAUTION!)
docker-compose down -v
```

### Update Configuration

```bash
# After editing prometheus.yml or alert_rules.yml
docker-compose restart prometheus

# After editing alertmanager.yml
docker-compose restart alertmanager

# Reload Prometheus without restart (faster)
curl -X POST http://localhost:9090/-/reload
```

---

## Troubleshooting

### Issue: Prometheus Shows Targets as "DOWN"

**Symptom**: In Prometheus UI (Status → Targets), automatictrader-api shows as DOWN

**Causes & Solutions**:

1. **Service not running**
   ```bash
   curl http://localhost:8080/healthz
   # If fails, start automatictrader-api
   ```

2. **Docker network issue** (can't resolve `host.docker.internal`)
   ```bash
   # Test from inside Prometheus container
   docker exec trading-prometheus ping host.docker.internal

   # If fails, update prometheus.yml to use server IP:
   # - targets: ['192.168.1.100:8080']  # Your Debian IP
   ```

3. **Firewall blocking**
   ```bash
   sudo ufw status
   # Ensure port 8080 accessible from localhost
   ```

### Issue: Grafana Shows "No Data"

**Solutions**:

1. Check Prometheus has data:
   ```bash
   curl 'http://localhost:9090/api/v1/query?query=up'
   ```

2. Check time range in Grafana (top right)

3. Verify data source connection (Configuration → Data Sources → Test)

### Issue: Out of Disk Space

**Check usage**:
```bash
docker system df
du -sh /var/lib/docker/volumes/monitoring_*
```

**Clean up**:
```bash
# Remove old Prometheus data (keeps last 7 days)
docker-compose down
docker volume rm monitoring_prometheus_data
docker-compose up -d
```

**Reduce retention**:
Edit `docker-compose.yml`:
```yaml
command:
  - '--storage.tsdb.retention.time=7d'  # Change from 30d
```

---

## Systemd Service (Optional - Auto-start on Boot)

Create `/etc/systemd/system/trading-monitoring.service`:

```ini
[Unit]
Description=Trading System Monitoring Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/trading/traderunner/monitoring
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-monitoring.service
sudo systemctl start trading-monitoring.service

# Check status
sudo systemctl status trading-monitoring
```

---

## Backup & Restore

### Backup

```bash
# Create backup directory
mkdir -p ~/trading-backups/$(date +%Y%m%d)

# Backup Prometheus data
docker run --rm \
  -v monitoring_prometheus_data:/data \
  -v ~/trading-backups/$(date +%Y%m%d):/backup \
  alpine tar czf /backup/prometheus-data.tar.gz /data

# Backup Grafana dashboards
docker run --rm \
  -v monitoring_grafana_data:/data \
  -v ~/trading-backups/$(date +%Y%m%d):/backup \
  alpine tar czf /backup/grafana-data.tar.gz /data

# Backup configuration
tar czf ~/trading-backups/$(date +%Y%m%d)/monitoring-config.tar.gz \
  /opt/trading/traderunner/monitoring/*.yml \
  /opt/trading/traderunner/monitoring/docker-compose.yml
```

### Restore

```bash
# Stop services
cd /opt/trading/traderunner/monitoring
docker-compose down

# Restore Prometheus data
docker run --rm \
  -v monitoring_prometheus_data:/data \
  -v ~/trading-backups/20241201:/backup \
  alpine sh -c "cd /data && tar xzf /backup/prometheus-data.tar.gz --strip 1"

# Restore Grafana data
docker run --rm \
  -v monitoring_grafana_data:/data \
  -v ~/trading-backups/20241201:/backup \
  alpine sh -c "cd /data && tar xzf /backup/grafana-data.tar.gz --strip 1"

# Restart
docker-compose up -d
```

---

## Performance Tuning

### Reduce Prometheus Memory Usage

Edit `docker-compose.yml`:

```yaml
prometheus:
  command:
    - '--storage.tsdb.retention.time=7d'      # Shorter retention
    - '--query.max-samples=5000000'          # Limit query samples
  deploy:
    resources:
      limits:
        memory: 512M                          # Set memory limit
```

### Prometheus Query Optimization

Use recording rules for expensive queries. Create `recording_rules.yml`:

```yaml
groups:
  - name: trading_recordings
    interval: 30s
    rules:
      - record: job:order_intent_processing_rate:5m
        expr: rate(order_intents_created_total[5m])

      - record: job:order_intent_error_rate:5m
        expr: rate(order_intents_error_total[5m]) / rate(order_intents_created_total[5m])
```

Add to `prometheus.yml`:
```yaml
rule_files:
  - 'recording_rules.yml'
```

---

## Next Steps

1. **Create Custom Dashboards** - Build trading-specific views
2. **Configure Alerts** - Set up Slack/Email notifications
3. **Add More Metrics** - Instrument marketdata-stream and position manager
4. **Security** - Set up HTTPS reverse proxy for remote access
5. **Monitoring the Monitor** - Set up external uptime checks

---

## Quick Reference Commands

```bash
# Start
cd /opt/trading/traderunner/monitoring && docker-compose up -d

# Stop
docker-compose down

# Logs
docker-compose logs -f

# Restart after config change
docker-compose restart prometheus

# Access from laptop
ssh -L 3000:localhost:3000 user@debian-server

# Check health
curl http://localhost:9090/-/healthy && \
curl http://localhost:3000/api/health && \
curl http://localhost:9093/-/healthy

# View targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'
```

---

## Support

- Prometheus Docs: https://prometheus.io/docs/
- Grafana Docs: https://grafana.com/docs/
- Alertmanager: https://prometheus.io/docs/alerting/latest/alertmanager/

For trading system specific issues, check logs:
- Prometheus: `docker-compose logs prometheus`
- Application: `/var/log/trading/` (if configured)
