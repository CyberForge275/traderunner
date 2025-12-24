# Deployment Automation

This directory contains automated deployment scripts for the trading system.

## deploy_to_debian.sh

Automated deployment script for Debian/Ubuntu servers.

### What It Does

This script automates the entire deployment process from the [Debian Deployment Checklist](file:///home/mirko/.gemini/antigravity/brain/898607f4-3a87-490c-aa2d-4a15159f33b4/debian_deployment_checklist.md):

1. ✅ Tests SSH connection to server
2. ✅ Creates remote directory structure
3. ✅ Copies `traderunner` and `automatictrader-api` via rsync
4. ✅ Sets up Python virtual environments
5. ✅ Installs dependencies
6. ✅ Configures environment (plan-only mode for safety)
7. ✅ Initializes database
8. ✅ Runs health check test
9. ✅ Optionally creates systemd services
10. ✅ Optionally starts services

### Usage

```bash
cd /home/mirko/data/workspace/droid/traderunner
./scripts/deploy_to_debian.sh
```

You will be prompted for:
- Server hostname/IP
- SSH username
- Whether to setup systemd services
- Whether to start services immediately

### Requirements

**On Local Machine:**
- SSH access to Debian server
- rsync installed
- Both projects in their workspace directories

**On Debian Server:**
- Python 3.9+
- sudo access (for systemd setup)
- SSH key authentication configured

### Safety Features

- Deploys in **plan-only mode** by default (no actual trading)
- Excludes `.git`, `__pycache__`, and data directories
- Tests SSH connection before proceeding
- Validates health check after deployment
- Prompts before setting up systemd services

### Post-Deployment

After successful deployment:

1. **Monitor the system:**
   ```bash
   ssh user@server
   sudo journalctl -u automatictrader-api -f
   ```

2. **Test signal generation:**
   ```bash
   cd /opt/trading/traderunner
   source .venv/bin/activate
   PYTHONPATH=src python -m signals.cli_rudometkin_moc \
     --symbols AAPL --start 2025-11-20 --end 2025-11-20
   ```

3. **Enable paper trading** (after 24h monitoring):
   ```bash
   ssh user@server
   nano /opt/trading/automatictrader-api/.env
   # Set: AT_WORKER_MODE=paper-send
   sudo systemctl restart automatictrader-worker
   ```

### Troubleshooting

If deployment fails:

- **SSH connection failed:** Check server hostname and SSH key setup
- **rsync errors:** Ensure source directories exist
- **pip install fails:** Verify Python 3.9+ is installed on server
- **Permission denied:** Ensure user has sudo access for systemd setup

### Manual Deployment

If you prefer manual control, follow the step-by-step [Debian Deployment Checklist](file:///home/mirko/.gemini/antigravity/brain/898607f4-3a87-490c-aa2d-4a15159f33b4/debian_deployment_checklist.md) instead.
