"""
Trading Dashboard Configuration
"""
import os
from pathlib import Path

# Server
PORT = int(os.getenv("DASHBOARD_PORT", "9001"))
HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DEBUG = os.getenv("DASHBOARD_DEBUG", "false").lower() == "true"

# Authentication
AUTH_USERNAME = os.getenv("DASHBOARD_USER", "admin")
AUTH_PASSWORD = os.getenv("DASHBOARD_PASS", "admin")

# Paths
BASE_DIR = Path(__file__).parent.parent
TRADERUNNER_DIR = BASE_DIR

# Use environment variables with server-appropriate defaults
MARKETDATA_DIR = Path(os.getenv("MARKETDATA_DIR", "/opt/trading/marketdata-stream"))
AUTOMATICTRADER_DIR = Path(os.getenv("AUTOMATICTRADER_DIR", "/opt/trading/automatictrader-api"))

# Databases
SIGNALS_DB = MARKETDATA_DIR / "data" / "signals.db"
TRADING_DB = AUTOMATICTRADER_DIR / "data" / "automatictrader.db"

# Strategy config
STRATEGY_CONFIG = MARKETDATA_DIR / "config" / "strategy_params.yaml"

# Update interval (milliseconds)
UPDATE_INTERVAL_MS = 5000

# Theme
THEME = "dark"
