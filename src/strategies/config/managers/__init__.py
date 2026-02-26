"""Import managers to trigger registry self-registration."""

from .confirmed_breakout_manager import ConfirmedBreakoutConfigManager
from .harami_break_manager import HaramiBreakConfigManager
from .inside_bar_manager import InsideBarConfigManager

__all__ = [
    "InsideBarConfigManager",
    "ConfirmedBreakoutConfigManager",
    "HaramiBreakConfigManager",
]
