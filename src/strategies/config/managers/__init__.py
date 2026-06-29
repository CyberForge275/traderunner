"""Import managers to trigger registry self-registration."""

from .confirmed_breakout_manager import ConfirmedBreakoutConfigManager
from .harami_break_manager import HaramiBreakConfigManager
from .inside_bar_manager import InsideBarConfigManager
from .ndx_momentum_rotation_manager import NdxMomentumRotationConfigManager
from .perlentaucher_daily_scan_manager import PerlentaucherDailyScanConfigManager

__all__ = [
    "InsideBarConfigManager",
    "ConfirmedBreakoutConfigManager",
    "HaramiBreakConfigManager",
    "NdxMomentumRotationConfigManager",
    "PerlentaucherDailyScanConfigManager",
]
