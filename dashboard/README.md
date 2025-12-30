# Trading System Status Dashboard

Lightweight HTML dashboard for monitoring your trading system deployment.

## Features

- 🎨 **Beautiful Modern UI** - Gradient design with glass-morphism effects
- 📊 **Real-time Status** - API, Worker, and Database monitoring
- ✅ **Sanity Check Integration** - Live sanity check results
- 🔄 **Auto-refresh** - Optional 30-second auto-refresh
- 📱 **Responsive** - Works on desktop and mobile
- ⚡ **Lightweight** - Pure HTML/CSS/JS, no frameworks

## Quick Start

### Deploy to Server

```bash
# Copy dashboard to server
rsync -avz dashboard/ mirko@192.168.178.55:/opt/trading/traderunner/dashboard/

# Start the server
ssh mirko@192.168.178.55 "cd /opt/trading/traderunner/dashboard && python3 server.py"
```

### Access Dashboard

Open in your browser:
```
http://192.168.178.55:9000
```

## Status Information

The dashboard displays:

### System Status
- **API Server** - Running status, port, and mode (plan-only/paper-send)
- **Worker** - Running status and configuration
- **Database** - Intent count and initialization status

### Sanity Check Results
- Passed tests (green)
- Warnings (yellow)
- Failed tests (red)
- Health progress bar

## API Endpoints

The dashboard server provides:

- `GET /` - Dashboard HTML page
- `GET /api/status` - JSON status data

### Status API Response

```json
{
  "api": {
    "running": true,
    "mode": "plan-only",
    "port": 8080
  },
  "worker": {
    "running": false
  },
  "database": {
    "initialized": true,
    "intent_count": 5
  },
  "sanity": {
    "passed": 24,
    "warnings": 3,
    "failed": 0
  }
}
```

## Running as a Service

### Manual Start
```bash
ssh mirko@192.168.178.55
cd /opt/trading/traderunner/dashboard
python3 server.py
```

### Systemd Service (Auto-start)

1. **Copy service file:**
```bash
ssh mirko@192.168.178.55
sudo cp /opt/trading/traderunner/dashboard/trading-dashboard.service /etc/systemd/system/
```

2. **Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-dashboard
sudo systemctl start trading-dashboard
```

3. **Check status:**
```bash
sudo systemctl status trading-dashboard
```

## Configuration

### Change Port

Edit `server.py` line 16:
```python
PORT = 9000  # Change to your preferred port
```

### Change Paths

Edit the configuration section in `server.py`:
```python
API_DIR = Path("/opt/trading/automatictrader-api")
RUNNER_DIR = Path("/opt/trading/traderunner")
DB_PATH = API_DIR / "data" / "automatictrader.db"
```

## Customization

### Update Refresh Interval

Edit `index.html` line 429:
```javascript
autoRefreshInterval = setInterval(refreshStatus, 30000);  // 30 seconds
```

### Styling

All styles are in the `<style>` section of `index.html`. The dashboard uses:
- Gradient backgrounds
- Glass-morphism effects
- Smooth animations
- Responsive grid layout

## Security

**Important:** The dashboard currently has no authentication.

For production:
1. Use a reverse proxy (nginx) with basic auth
2. Only allow access from trusted IPs
3. Use firewall rules to restrict port access

Example firewall rule:
```bash
sudo ufw allow from 192.168.178.0/24 to any port 9000
```

## Troubleshooting

### Dashboard not accessible

```bash
# Check if server is running
ssh mirko@192.168.178.55 "ps aux | grep 'python3.*server.py'"

# Check port
ssh mirko@192.168.178.55 "lsof -i :9000"

# Check logs
ssh mirko@192.168.178.55 "journalctl -u trading-dashboard -f"
```

### Status not updating

```bash
# Check API endpoint
curl http://192.168.178.55:9000/api/status

# Check sanity script exists
ssh mirko@192.168.178.55 "ls -la /opt/trading/traderunner/scripts/sanity_check.sh"
```

## Development

Test locally before deploying:

```bash
cd /home/mirko/data/workspace/droid/traderunner/dashboard
# Update paths in server.py to point to local directories
python3 server.py
# Open http://localhost:9000
```

## Files

- `index.html` - Dashboard UI
- `server.py` - Python HTTP server with status API
- `trading-dashboard.service` - Systemd service file
