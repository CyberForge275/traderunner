"""
Trading System Settings
========================

12-Factor compliant configuration management using dataclasses.

Settings are loaded from:
1. Environment variables (highest priority)
2. .env file (if exists)
3. Default values (fallback)

Usage:
    from src.core.settings import get_settings

    settings = get_settings()
    data_root = settings.data_root
    signals_db = settings.signals_db_path
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

# Try to load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip
    pass


class Environment(str, Enum):
    """Deployment environment."""
    DEV = "dev"
    TEST = "test"
    PRODUCTION = "production"


@dataclass
class TradingSettings:
    """
    Central configuration for trading system.

    All hard-coded paths are eliminated and configured here.
    """

    # ===== Environment =====
    environment: Environment = field(default=Environment.DEV)

    # ===== Project Roots =====
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[3])

    # ===== Production Detection =====
    is_production_server: bool = field(default=False)
    production_base_path: Path = field(default_factory=lambda: Path("/opt/trading"))

    # ===== Data Directories =====
    data_root: Optional[Path] = None
    data_m1_dir: Optional[Path] = None
    data_m5_dir: Optional[Path] = None
    data_m15_dir: Optional[Path] = None
    data_h1_dir: Optional[Path] = None
    data_d1_dir: Optional[Path] = None

    # ===== Artifacts =====
    artifacts_root: Optional[Path] = None
    signals_dir: Optional[Path] = None
    backtests_dir: Optional[Path] = None

    # ===== Configuration =====
    config_root: Optional[Path] = None

    # ===== Logs =====
    logs_root: Optional[Path] = None

    # ===== Databases =====
    signals_db_path: Optional[Path] = None
    market_data_db_path: Optional[Path] = None
    analytics_db_path: Optional[Path] = None

    # ===== External Directories =====
    marketdata_stream_dir: Optional[Path] = None
    automatictrader_api_dir: Optional[Path] = None

    def __post_init__(self):
        """Initialize settings and compute derived paths."""
        # Load from environment variables
        self._load_from_env()

        # Auto-detect production
        if self.production_base_path.exists() and not self.data_root:
            self.is_production_server = True

        # Set defaults
        self._set_defaults()

    def _load_from_env(self):
        """Load settings from environment variables."""
        # Environment
        env_str = os.getenv("TRADING_ENVIRONMENT", "dev")
        try:
            self.environment = Environment(env_str)
        except ValueError:
            pass

        # Production detection
        if os.getenv("TRADING_IS_PRODUCTION_SERVER", "").lower() == "true":
            self.is_production_server = True

        prod_base = os.getenv("TRADING_PRODUCTION_BASE_PATH")
        if prod_base:
            self.production_base_path = Path(prod_base)

        # Data directories
        if data_root := os.getenv("TRADING_DATA_ROOT"):
            self.data_root = Path(data_root)
        if data_m1 := os.getenv("TRADING_DATA_M1_DIR"):
            self.data_m1_dir = Path(data_m1)
        if data_m5 := os.getenv("TRADING_DATA_M5_DIR"):
            self.data_m5_dir = Path(data_m5)
        if data_d1 := os.getenv("TRADING_DATA_D1_DIR"):
            self.data_d1_dir = Path(data_d1)

        # Databases
        if signals_db := os.getenv("TRADING_SIGNALS_DB_PATH"):
            self.signals_db_path = Path(signals_db)
        if market_db := os.getenv("TRADING_MARKET_DATA_DB_PATH"):
            self.market_data_db_path = Path(market_db)

    def _set_defaults(self):
        """Set default paths based on environment."""
        # Determine base paths
        if self.is_production_server:
            traderunner_root = self.production_base_path / "traderunner"
            marketdata_root = self.production_base_path / "marketdata-stream"
        else:
            traderunner_root = self.project_root
            marketdata_root = self.project_root.parent / "marketdata-stream"
            if not marketdata_root.exists():
                marketdata_root = self.project_root.parent.parent / "marketdata-stream"

        # Data root
        if not self.data_root:
            if self.is_production_server:
                self.data_root = marketdata_root / "data"
            else:
                self.data_root = traderunner_root / "artifacts"

        # Timeframe data directories
        if not self.data_m1_dir:
            self.data_m1_dir = self.data_root / "data_m1"
        if not self.data_m5_dir:
            self.data_m5_dir = self.data_root / "data_m5"
        if not self.data_m15_dir:
            self.data_m15_dir = self.data_root / "data_m15"
        if not self.data_h1_dir:
            self.data_h1_dir = self.data_root / "data_h1"
        if not self.data_d1_dir:
            self.data_d1_dir = traderunner_root / "artifacts" / "data_d1"

        # Artifacts
        if not self.artifacts_root:
            self.artifacts_root = traderunner_root / "artifacts"
        if not self.signals_dir:
            self.signals_dir = self.artifacts_root / "signals"
        if not self.backtests_dir:
            self.backtests_dir = self.artifacts_root / "backtests"

        # Config
        if not self.config_root:
            self.config_root = traderunner_root / "config"

        # Logs
        if not self.logs_root:
            self.logs_root = traderunner_root / "logs"

        # Databases
        if not self.signals_db_path:
            if self.is_production_server:
                self.signals_db_path = marketdata_root / "data" / "signals.db"
            else:
                self.signals_db_path = self.artifacts_root / "signals.db"

        if not self.market_data_db_path:
            if self.is_production_server:
                self.market_data_db_path = marketdata_root / "data" / "market_data.db"
            else:
                self.market_data_db_path = self.data_root / "market_data.db"

        # External directories
        if not self.marketdata_stream_dir:
            self.marketdata_stream_dir = marketdata_root

        if not self.automatictrader_api_dir:
            if self.is_production_server:
                self.automatictrader_api_dir = self.production_base_path / "automatictrader-api"
            else:
                self.automatictrader_api_dir = self.project_root.parent / "automatictrader-api"

    def get_timeframe_dir(self, timeframe: str) -> Path:
        """
        Get data directory for timeframe.

        Args:
            timeframe: Timeframe code (M1, M5, M15, H1, D1)

        Returns:
            Path to timeframe data directory
        """
        timeframe_map = {
            "M1": self.data_m1_dir,
            "M5": self.data_m5_dir,
            "M15": self.data_m15_dir,
            "H1": self.data_h1_dir,
            "D1": self.data_d1_dir,
        }

        if timeframe not in timeframe_map:
            raise ValueError(f"Unknown timeframe: {timeframe}")

        return timeframe_map[timeframe]


# Singleton instance
_settings: Optional[TradingSettings] = None


def get_settings() -> TradingSettings:
    """
    Get singleton settings instance.

    Returns:
        TradingSettings instance
    """
    global _settings

    if _settings is None:
        _settings = TradingSettings()

    return _settings


def reset_settings():
    """
    Reset settings (for testing).

    WARNING: Only use in tests!
    """
    global _settings
    _settings = None
