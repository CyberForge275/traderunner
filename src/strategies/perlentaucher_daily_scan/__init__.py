"""Perlentaucher daily scan strategy skeleton."""

from strategies.registry import register_strategy

from . import debug_hooks
from .plugin import PerlentaucherDailyScanPlugin
from . import scan_runner

register_strategy(PerlentaucherDailyScanPlugin())

__all__ = ["PerlentaucherDailyScanPlugin", "debug_hooks", "scan_runner"]
