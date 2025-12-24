# Quick Deployment Checklist

## On Debian Server

### 1. Transfer Files

```bash
# From your laptop
cd /home/mirko/data/workspace/droid/traderunner
scp -r monitoring/ user@debian-server:/opt/trading/traderunner/
```

### 2. Start Monitoring Stack

```bash
# SSH to server
ssh user@debian-server

# Navigate to monitoring directory
cd /opt/trading/traderunner/monitoring

# Start services
docker-compose up -d

# Verify
docker-compose ps
```

### 3. Verify Services Running

```bash
# Quick health check
curl http://localhost:9090/-/healthy && echo "✅ Prometheus OK"
curl http://localhost:3000/api/health && echo "✅ Grafana OK"  
curl http://localhost:9093/-/healthy && echo "✅ Alertmanager OK"

# Check if Prometheus is scraping automatictrader-api
curl http://localhost:9090/api/v1/targets | grep automatictrader-api -A 5
```

### 4. Access from Your Laptop

```bash
# Create SSH tunnel
ssh -L 3000:localhost:3000 -L 9090:localhost:9090 user@debian-server

# Open browser
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

### 5. First Login to Grafana

1. Go to http://localhost:3000
2. Login: `admin` / `admin`
3. Change password when prompted
4. Dashboard "Trading System Overview" should be automatically loaded
5. Click on it to view metrics!

---

## Expected Result

You should see:
- ✅ Order Intent Flow graph showing pending/planned/ready/sent counts
- ✅ Creation Rate showing intents per minute
- ✅ Status distribution pie chart
- ✅ API request duration
- ✅ Error rate and success rate stats
- ✅ Worker status (UP/DOWN)

---

## Troubleshooting

### Targets show as DOWN in Prometheus

**Check if automatictrader-api is running:**
```bash
curl http://localhost:8080/healthz
```

**If not running, start it:**
```bash
cd /opt/trading/automatictrader-api
python -m uvicorn app:app --host 0.0.0.0 --port 8080
```

### No data in Grafana

**Check time range** - Click time picker (top right), set to "Last 15 minutes"

**Verify Prometheus has data:**
```bash
curl 'http://localhost:9090/api/v1/query?query=up{job="automatictrader-api"}'
```

### Docker network issues

If `host.docker.internal` doesn't work, edit `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'automatictrader-api'
    static_configs:
      - targets: ['localhost:8080']  # Change from host.docker.internal
```

Then restart:
```bash
docker-compose restart prometheus
```

---

## Next Steps After Deployment

1. **Test Alert Rules** - Stop a service and verify alert fires
2. **Configure Slack/Email** - Update `alertmanager.yml` with webhook
3. **Add marketdata-stream metrics** - Instrument with Prometheus client
4. **Create custom dashboards** - Build views specific to your strategies
5. **Set up systemd service** - Auto-start monitoring on server boot

---

## Files Summary

**Configuration:**
- `prometheus.yml` - Metrics scraping config
- `alert_rules.yml` - Alert definitions
- `alertmanager.yml` - Alert routing
- `docker-compose.yml` - Service orchestration

**Grafana:**
- `grafana/provisioning/datasources/prometheus.yml` - Auto-configure Prometheus
- `grafana/provisioning/dashboards/dashboards.yml` - Auto-load dashboards
- `grafana/dashboards/trading_overview.json` - Trading dashboard

**Documentation:**
- `README.md` - General monitoring guide
- `DEBIAN_DEPLOYMENT.md` - Detailed server deployment
- `QUICKSTART.md` - This file

---

For detailed information, see `DEBIAN_DEPLOYMENT.md`.
