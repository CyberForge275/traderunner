"""InsideBar strategy package - Unified implementation."""

from .core import InsideBarCore, InsideBarConfig, RawSignal
from .config import load_config, get_default_config_path, load_default_config

__version__ = "2.0.0"

__all__ = [
    "InsideBarCore",
    "InsideBarConfig",
    "RawSignal",
    "load_config",
    "get_default_config_path",
    "load_default_config",
]
