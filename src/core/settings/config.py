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


class TradingSettings(BaseSettings):
    """
    Central configuration for trading system.
    
    All hard-coded paths should be eliminated and configured here.
    """
    
    # ===== Environment =====
    environment: Environment = Field(
        default=Environment.DEV,
        description="Deployment environment"
    )
    
    # ===== Project Roots =====
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3],
        description="Project root directory"
    )
    
    # ===== Data Directories =====
    data_root: Path = Field(
        default=None,
        description="Root directory for market data"
    )
    
    data_m1_dir: Optional[Path] = Field(
        default=None,
        description="M1 intraday data directory"
    )
    
    data_m5_dir: Optional[Path] = Field(
        default=None,
        description="M5 intraday data directory"
    )
    
    data_m15_dir: Optional[Path] = Field(
        default=None,
        description="M15 intraday data directory"
    )
    
    data_h1_dir: Optional[Path] = Field(
        default=None,
        description="H1 intraday data directory"
    )
    
    data_d1_dir: Optional[Path] = Field(
        default=None,
        description="D1 daily data directory"
    )
    
    # ===== Artifacts =====
    artifacts_root: Path = Field(
        default=None,
        description="Root directory for artifacts (signals, backtests, etc.)"
    )
    
    signals_dir: Optional[Path] = Field(
        default=None,
        description="Generated signals directory"
    )
    
    backtests_dir: Optional[Path] = Field(
        default=None,
        description="Backtest results directory"
    )
    
    # ===== Configuration =====
    config_root: Path = Field(
        default=None,
        description="Strategy configuration files directory"
    )
    
    # ===== Logs =====
    logs_root: Path = Field(
        default=None,
        description="Log files directory"
    )
    
    # ===== Databases =====
    signals_db_path: Path = Field(
        default=None,
        description="Path to signals.db SQLite database"
    )
    
    market_data_db_path: Path = Field(
        default=None,
        description="Path to market_data.db SQLite database"
    )
    
    analytics_db_path: Optional[Path] = Field(
        default=None,
        description="Path to analytics database"
    )
    
    # ===== ClickHouse (Optional) =====
    clickhouse_host: Optional[str] = Field(
        default=None,
        description="ClickHouse host"
    )
    
    clickhouse_port: int = Field(
        default=8123,
        description="ClickHouse HTTP port"
    )
    
    clickhouse_database: Optional[str] = Field(
        default=None,
        description="ClickHouse database name"
    )
    
    # ===== External Services =====
    eodhd_api_key: Optional[str] = Field(
        default=None,
        description="EODHD API key for data fetching"
    )
    
    # ===== External Directories (for integration) =====
    marketdata_stream_dir: Optional[Path] = Field(
        default=None,
        description="marketdata-stream project directory"
    )
    
    automatictrader_api_dir: Optional[Path] = Field(
        default=None,
        description="automatictrader-api project directory"
    )
    
    # ===== Server Paths (Production) =====
    is_production_server: bool = Field(
        default=False,
        description="Whether running on production server"
    )
    
    production_base_path: Path = Field(
        default=Path("/opt/trading"),
        description="Base path on production server"
    )
    
    def __init__(self, **kwargs):
        """Initialize settings and compute derived paths."""
        super().__init__(**kwargs)
        
        # Auto-detect production environment
        if self.production_base_path.exists() and not self.data_root:
            self.is_production_server = True
        
        # Set defaults based on environment
        self._set_defaults()
    
    def _set_defaults(self):
        """Set default paths based on environment."""
        # Determine base paths
        if self.is_production_server:
            traderunner_root = self.production_base_path / "traderunner"
            marketdata_root = self.production_base_path / "marketdata-stream"
        else:
            traderunner_root = self.project_root
            marketdata_root = self.project_root.parent / "marketdata-stream"
        
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
            if self.is_production_server:
                self.marketdata_stream_dir = self.production_base_path / "marketdata-stream"
            else:
                self.marketdata_stream_dir = self.project_root.parent / "marketdata-stream"
        
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
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_prefix = "TRADING_"
        case_sensitive = False


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
