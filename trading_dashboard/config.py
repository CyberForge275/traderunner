"""
Dashboard Configuration
========================

Central configuration for trading_dashboard.
Now uses src.core.settings for all paths - NO MORE HARD-CODED PATHS!
"""

import os
from pathlib import Path

# Import central Settings
from src.core.settings import get_settings

# Get settings instance
settings = get_settings()

# ===== Paths (from Settings) =====
PROJECT_ROOT = settings.project_root
MARKETDATA_DIR = settings.marketdata_stream_dir
AUTOMATICTRADER_DIR = settings.automatictrader_api_dir

# Data directories
DATA_M5_DIR = settings.data_m5_dir
DATA_D1_DIR = settings.data_d1_dir

# Config directory
CONFIG_DIR = settings.config_root

# Database paths
SIGNALS_DB = settings.signals_db_path
MARKET_DATA_DB = settings.market_data_db_path

# Artifacts
ARTIFACTS_DIR = settings.artifacts_root
BACKTEST_RESULTS_DIR = settings.backtests_dir

# ===== Dashboard Settings =====
DASHBOARD_TITLE = "Trading Dashboard"
PORT = int(os.getenv("DASHBOARD_PORT", "9001"))
HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DEBUG = os.getenv("DASHBOARD_DEBUG", "false").lower() == "true"

# Authentication
AUTH_USERNAME = os.getenv("DASHBOARD_USER", "admin")
AUTH_PASSWORD = os.getenv("DASHBOARD_PASS", "admin")

# Update interval (milliseconds)
UPDATE_INTERVAL_MS = 5000

# Theme
THEME = "dark"

# ===== Logging =====
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = settings.logs_root / "dashboard.log"

# ===== API Settings (optional) =====
EODHD_API_KEY = os.getenv("EODHD_API_KEY")

# Legacy compatibility (kept for backward compatibility)
TRADERUNNER_DIR = PROJECT_ROOT
BACKTESTS_DIR = BACKTEST_RESULTS_DIR
TRADING_DB = AUTOMATICTRADER_DIR / "data" / "automatictrader.db" if AUTOMATICTRADER_DIR else None
STRATEGY_CONFIG = MARKETDATA_DIR / "config" / "strategy_params.yaml" if MARKETDATA_DIR else None
