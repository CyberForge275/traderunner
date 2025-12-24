"""Core settings and configuration for traderunner project.

This module provides centralized configuration,including paths, database locations,
and runtime settings. All components should import settings from here to ensure
consistency across the project.
"""

import os
from pathlib import Path
from typing import Optional


# Detect project root (where traderunner is located)
def _detect_project_root() -> Path:
    """Detect traderunner project root directory.

    Logic:
    1. If running from /opt/trading/traderunner -> use that
    2. If CWD contains 'traderunner' -> use parent or CWD
    3. Fallback: current working directory
    """
    cwd = Path.cwd()

    # INT production path
    if cwd.as_posix().startswith("/opt/trading/traderunner"):
        return Path("/opt/trading/traderunner")

    # Development: find traderunner in path
    if "traderunner" in cwd.parts:
        # Navigate up until we find traderunner
        for parent in [cwd] + list(cwd.parents):
            if parent.name == "traderunner":
                return parent

    # Fallback: assume CWD is project root
    return cwd


# Project paths
PROJECT_ROOT = _detect_project_root()
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"

# Intraday data directories (canonical paths)
DATA_M1_DIR = ARTIFACTS_ROOT / "data_m1"
DATA_M5_DIR = ARTIFACTS_ROOT / "data_m5"
DATA_M15_DIR = ARTIFACTS_ROOT / "data_m15"
DATA_D1_DIR = ARTIFACTS_ROOT / "data_d1"

# Other artifact directories
BACKTESTS_DIR = ARTIFACTS_ROOT / "backtests"
LOGS_DIR = ARTIFACTS_ROOT / "logs"
DATA_DIR = ARTIFACTS_ROOT / "data"
UNIVERSE_DIR = ARTIFACTS_ROOT / "universe"

# Databases (relative to project root or ENV override)
SIGNALS_DB_PATH = Path(os.getenv("SIGNALS_DB_PATH", "./data/signals.db"))
MARKET_DATA_DB_PATH = Path(os.getenv("MARKET_DATA_DB_PATH", "./data/market_data.db"))

# External directories (sibling projects)
MARKETDATA_STREAM_DIR = PROJECT_ROOT.parent / "marketdata-stream" if (PROJECT_ROOT/ ".." / "marketdata-stream").exists() else None
AUTOMATICTRADER_API_DIR = PROJECT_ROOT.parent / "automatictrader-api" if (PROJECT_ROOT.parent / "automatictrader-api").exists() else None

# Runtime settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENABLE_CONTRACTS = os.getenv("ENABLE_CONTRACTS", "false").lower() == "true"


def ensure_artifact_layout() -> None:
    """Create canonical artifact directory structure."""
    for directory in [
        ARTIFACTS_ROOT,
        DATA_M1_DIR,
        DATA_M5_DIR,
        DATA_M15_DIR,
        DATA_D1_DIR,
        BACKTESTS_DIR,
        LOGS_DIR,
        DATA_DIR,
        UNIVERSE_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


# Settings class for compatibility with existing code
class Settings:
    """Settings object for backward compatibility."""

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.artifacts_root = ARTIFACTS_ROOT

        # Data directories
        self.data_m1_dir = DATA_M1_DIR
        self.data_m5_dir = DATA_M5_DIR
        self.data_m15_dir = DATA_M15_DIR
        self.data_d1_dir = DATA_D1_DIR

        # Other directories
        self.backtests_dir = BACKTESTS_DIR
        self.logs_root = LOGS_DIR
        self.data_dir = DATA_DIR
        self.universe_dir = UNIVERSE_DIR

        # Databases
        self.signals_db_path = SIGNALS_DB_PATH
        self.market_data_db_path = MARKET_DATA_DB_PATH

        # External
        self.marketdata_stream_dir = MARKETDATA_STREAM_DIR
        self.automatictrader_api_dir = AUTOMATICTRADER_API_DIR

        # Config
        self.config_root = PROJECT_ROOT / "config"

    def ensure_layout(self):
        """Ensure artifact directories exist."""
        ensure_artifact_layout()


# Singleton instance
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get singleton settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
