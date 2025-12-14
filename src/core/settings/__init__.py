"""
Core Settings Package
=====================

Central configuration management for all environment-specific settings.

This package provides:
- TradingSettings: Environment-aware configuration dataclass
- get_settings(): Singleton settings factory
- Constants: Strategy defaults, initial cash, fees, etc.
"""

from .config import TradingSettings, get_settings
from .constants import (
    DEFAULT_INITIAL_CASH,
    DEFAULT_RISK_PCT,
    DEFAULT_MIN_QTY,
    DEFAULT_FEE_BPS,
    DEFAULT_SLIPPAGE_BPS,
    INSIDE_BAR_TIMEZONE,
    INSIDE_BAR_SESSIONS,
    INSIDE_BAR_DEFAULT_DATA_TZ,
    StrategyDefaults,
    INSIDE_BAR_DEFAULTS,
)

__all__ = [
    "TradingSettings",
    "get_settings",
    "DEFAULT_INITIAL_CASH",
    "DEFAULT_RISK_PCT",
    "DEFAULT_MIN_QTY",
    "DEFAULT_FEE_BPS",
    "DEFAULT_SLIPPAGE_BPS",
    "INSIDE_BAR_TIMEZONE",
    "INSIDE_BAR_SESSIONS",
    "INSIDE_BAR_DEFAULT_DATA_TZ",
    "StrategyDefaults",
    "INSIDE_BAR_DEFAULTS",
]

__version__ = "1.0.0"
