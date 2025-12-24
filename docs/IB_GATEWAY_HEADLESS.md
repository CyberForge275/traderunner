# Running IB Gateway Headless on Debian Server

## Overview

Interactive Brokers Gateway (IB Gateway) can run on a headless Debian server without a full GUI using **Xvfb** (X Virtual Framebuffer). This allows TWS/Gateway to run completely in the background.

## Why IB Gateway Instead of TWS?

- **IB Gateway**: Lighter, API-focused, no trading UI needed
- **TWS (Trader Workstation)**: Full trading platform with GUI (heavier)

For automated trading, **use IB Gateway**.

## Installation Steps

### 1. Install Java and Xvfb

```bash
ssh mirko@192.168.178.55

# Install Java (required for IB Gateway)
sudo apt-get update
sudo apt-get install -y openjdk-11-jre-headless

# Install Xvfb (virtual X server)
sudo apt-get install -y xvfb

# Install x11vnc (optional, for remote viewing/debugging)
sudo apt-get install -y x11vnc
```

### 2. Download and Install IB Gateway

```bash
cd /opt/trading
mkdir -p ibgateway
cd ibgateway

# Download IB Gateway (Linux version)
# Visit: https://www.interactivebrokers.com/en/index.php?f=16457
# Or use wget (check IB website for latest version):
wget https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/ibgateway-latest-standalone-linux-x64.sh

# Make executable
chmod +x ibgateway-*-linux-x64.sh

# Run installer
./ibgateway-*-linux-x64.sh -q
```

### 3. Configure IB Gateway

Edit the configuration file:
```bash
nano ~/Jts/jts.ini
```

Set API port for paper trading:
```ini
[IBGateway]
ApiOnly=true
ReadOnlyApi=false
TrustedIPs=127.0.0.1
```

### 4. Create Systemd Service for IB Gateway

Create `/etc/systemd/system/ibgateway.service`:

```ini
[Unit]
Description=IB Gateway (Headless)
After=network.target

[Service]
Type=simple
User=trading
Environment="DISPLAY=:99"
ExecStartPre=/usr/bin/Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
ExecStart=/home/trading/Jts/ibgateway/2024/ibgateway \
    -version=latest \
    -mode=paper \
    -user=YOUR_IB_USERNAME \
    -pw=YOUR_IB_PASSWORD
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

**Security Note**: For production, use IBC (IB Controller) to manage credentials more securely.

### 5. Alternative: Using IBC (IB Controller)

**IBC** is a better solution for production - it handles:
- Automatic login
- Session management
- Auto-restart on disconnects
- Secure credential handling

Install IBC:
```bash
cd /opt/trading
git clone https://github.com/IbcAlpha/IBC.git
cd IBC
./build.sh
```

Configure `/opt/trading/IBC/config.ini`:
```ini
IbLoginId=YOUR_IB_USERNAME
PasswordEncrypted=no
Password=YOUR_IB_PASSWORD
TradingMode=paper
IbApiPort=4002
AcceptIncomingConnectionAction=accept
```

### 6. Start IB Gateway with Xvfb

**Manual start (for testing):**
```bash
# Start Xvfb on display :99
Xvfb :99 -screen 0 1024x768x24 &

# Export DISPLAY
export DISPLAY=:99

# Start IB Gateway
~/Jts/ibgateway/*/ibgateway &
```

**With systemd (production):**
```bash
sudo systemctl daemon-reload
sudo systemctl enable ibgateway
sudo systemctl start ibgateway

# Check status
sudo systemctl status ibgateway
```

## Testing the Setup

### Check if IB Gateway is Running

```bash
# Check process
ps aux | grep ibgateway

# Check if API port is open
netstat -tuln | grep 4002
```

### Test Connection from automatictrader-api

```bash
cd /opt/trading/automatictrader-api
source .venv/bin/activate

# Test script (create this)
python << EOF
from ib_insync import IB
ib = IB()
try:
    ib.connect('127.0.0.1', 4002, clientId=17)
    print("✓ Connected to IB Gateway!")
    print(f"Account: {ib.managedAccounts()}")
    ib.disconnect()
except Exception as e:
    print(f"✗ Connection failed: {e}")
EOF
```

## Troubleshooting

### View Xvfb Display (for debugging)

If you need to see what's happening:

```bash
# On server, start x11vnc
x11vnc -display :99 -forever -nopw

# From your local machine
ssh -L 5900:localhost:5900 mirko@192.168.178.55
# Then connect with VNC client to localhost:5900
```

### Common Issues

**IB Gateway won't start:**
- Check Java is installed: `java -version`
- Check Xvfb is running: `ps aux | grep Xvfb`
- Check logs: `journalctl -u ibgateway -f`

**Connection refused:**
- Verify port 4002 is open: `netstat -tuln | grep 4002`
- Check firewall: `sudo ufw status`
- Verify trusted IPs in jts.ini

## Production Deployment Workflow

1. **Install dependencies** (Java, Xvfb)
2. **Install IB Gateway**
3. **Setup IBC** for credential management
4. **Create systemd service**
5. **Test connection** with paper trading
6. **Monitor for 24h** before enabling in automatictrader-api
7. **Update .env** to enable IB backend

## Summary

✅ **No full X-Server or GUI needed**  
✅ **Runs completely in background**  
✅ **Xvfb provides virtual display**  
✅ **IBC handles auto-login and session management**  
✅ **Systemd manages service lifecycle**  

This setup is perfect for headless servers!
