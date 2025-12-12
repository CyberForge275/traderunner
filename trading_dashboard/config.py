"""
Trading Dashboard Configuration
"""
Dashboard Configuration
========================

Central configuration for trading_dashboard.
Now uses src.core.settings for all paths - NO MORE HARD-CODED PATHS!
"""

import os
from pathlib import Path


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
