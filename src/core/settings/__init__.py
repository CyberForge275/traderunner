"""
Core Settings Package
=====================

Central configuration management for all environment-specific settings.

This package eliminates hard-coded paths and provides 12-Factor-compliant
configuration management.
"""

from .config import TradingSettings, get_settings

__all__ = ["TradingSettings", "get_settings"]

__version__ = "1.0.0"
