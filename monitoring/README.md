# Trading System Monitoring

Prometheus + Grafana + Alertmanager monitoring stack for the automated trading system.

## Quick Start

### 1. Start the Monitoring Stack

```bash
cd monitoring/
docker-compose up -d
```

### 2. Access Dashboards

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Alertmanager**: http://localhost:9093

### 3. Verify Services

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check Grafana health
curl http://localhost:3000/api/health

# Check automatictrader-api metrics
curl http://localhost:8080/metrics
```

##  Services Overview

### Prometheus (Port 9090)

Metrics collection and storage:
- Scrapes automatictrader-api every 15s
- Scrapes marketdata-stream every 15s
- Retains data for 30 days
- Evaluates alert rules every 30s

### Grafana (Port 3000)

Visualization dashboards:
- Trading Overview: Real-time order flow and P&L
- System Health: Service uptime and performance
- Worker Performance: Intent processing metrics

Default login: `admin` / `admin` (change on first login)

### Alertmanager (Port 9093)

Alert routing and notification:
- Groups alerts by severity
- Routes to file-based webhooks initially
- Configurable for Slack/Email/SMS

## Metrics Available

### automatictrader-api

**Counters:**
- `order_intents_created_total` - Total intents created
- `order_intents_duplicate_total` - Duplicate submissions (idempotency)
- `order_intents_error_total` - Intent creation errors

**Gauges:**
- `order_intents_pending` - Current pending count
- `order_intents_planned` - Current planned count
- `order_intents_ready` - Current ready count
- `order_intents_sent` - Current sent count

**Histograms:**
- `api_request_duration_seconds` - Request duration by endpoint

### Future: marketdata-stream

- Connection status
- Tick rate per symbol
- WebSocket uptime

### Future: Position Manager

- `daily_pnl` - Real-time P&L
- `position_reconciliation_discrepancy` - IB reconciliation errors
- `avg_slippage_pct` - Execution quality

## Alert Rules

See `alert_rules.yml` for full configuration.

### Critical Alerts

- `APIHealthCheckFailed` - Service down > 2 min
- `TWSConnectionLost` - IB connection errors
- `DailyLossLimitBreach` - P&L < -$500

### Warning Alerts

- `OrderIntentErrorRateHigh` - Error rate > 5%
- `OrderIntentsPendingTooMany` - > 50 pending for 10 min
- `WorkerProcessingLag` - Worker falling behind
- `UnusualSlippage` - Avg slippage > 0.5%
- `HighOrderRejectionRate` - Rejection rate > 10%

## Configuration

### Adding Notification Channels

#### Slack

Edit `alertmanager.yml`:

```yaml
receivers:
  - name: 'slack-alerts'
    slack_configs:
      - api_url: 'YOUR_WEBHOOK_URL'
        channel: '#trading-alerts'
```

#### Email

```yaml
receivers:
  - name: 'email-alerts'
    email_configs:
      - to: 'alerts@example.com'
        from: 'trading-system@example.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'user@gmail.com'
        auth_password: 'app-password'
```

Restart alertmanager:

```bash
docker-compose restart alertmanager
```

## Troubleshooting

### Prometheus can't scrape targets

**Symptom:** Targets show as "DOWN" in Prometheus UI

**Solution:**
- Verify services are running: `curl http://localhost:8080/healthz`
- Check `host.docker.internal` resolves (Docker Desktop feature)
- On Linux, use `--network=host` in docker-compose or configure bridge networking

### No data in Grafana

1. Check Prometheus datasource in Grafana (Configuration → Data Sources)
2. Verify metrics are being collected: `curl http://localhost:9090/api/v1/query?query=up`
3. Check dashboard time range

### Alerts not firing

1. Verify alert rules loaded: http://localhost:9090/alerts
2. Check Alertmanager config: http://localhost:9093
3. Review Prometheus logs: `docker-compose logs prometheus`

## Maintenance

### Backup

```bash
# Backup Prometheus data
docker run --rm -v monitoring_prometheus_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/prometheus-backup.tar.gz /data

# Backup Grafana dashboards
docker run --rm -v monitoring_grafana_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/grafana-backup.tar.gz /data
```

### Upgrade

```bash
docker-compose pull
docker-compose up -d
```

### Clean Up

```bash
# Stop and remove containers (keeps data)
docker-compose down

# Remove all data (CAUTION!)
docker-compose down -v
```

## Next Steps

1. **Create Grafana Dashboards** - Import or build custom dashboards
2. **Add Slack Integration** - Configure webhook for real-time alerts
3. **Tune Alert Thresholds** - Adjust based on observed behavior
4. **Add Position Metrics** - Instrument position manager for P&L tracking
