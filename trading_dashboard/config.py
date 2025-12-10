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

# Smart path detection for local vs server deployment
# Server paths (production)
MARKETDATA_DIR_SERVER = Path(os.getenv("MARKETDATA_DIR", "/opt/trading/marketdata-stream"))
AUTOMATICTRADER_DIR_SERVER = Path(os.getenv("AUTOMATICTRADER_DIR", "/opt/trading/automatictrader-api"))

# Local workspace paths (development)
MARKETDATA_DIR_LOCAL = BASE_DIR.parent / "marketdata-stream"
AUTOMATICTRADER_DIR_LOCAL = BASE_DIR.parent.parent / "automatictrader-api"

# Auto-detect environment: use server paths if they exist, otherwise use local
if MARKETDATA_DIR_SERVER.exists():
    MARKETDATA_DIR = MARKETDATA_DIR_SERVER
else:
    MARKETDATA_DIR = MARKETDATA_DIR_LOCAL
    print(f"Using local MARKETDATA_DIR: {MARKETDATA_DIR}")

if AUTOMATICTRADER_DIR_SERVER.exists():
    AUTOMATICTRADER_DIR = AUTOMATICTRADER_DIR_SERVER
else:
    AUTOMATICTRADER_DIR = AUTOMATICTRADER_DIR_LOCAL
    print(f"Using local AUTOMATICTRADER_DIR: {AUTOMATICTRADER_DIR}")

# Databases
SIGNALS_DB = MARKETDATA_DIR / "data" / "signals.db"
TRADING_DB = AUTOMATICTRADER_DIR / "data" / "automatictrader.db"

# Backtest artifacts (TradeRunner)
BACKTESTS_DIR = TRADERUNNER_DIR / "artifacts" / "backtests"

# Strategy config
STRATEGY_CONFIG = MARKETDATA_DIR / "config" / "strategy_params.yaml"

# Update interval (milliseconds)
UPDATE_INTERVAL_MS = 5000

# Theme
THEME = "dark"
