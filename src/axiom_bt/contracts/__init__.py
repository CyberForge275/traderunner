"""
Data contracts for v2 architecture.

This module defines strict contracts for data validation throughout
the trading pipeline to ensure data quality and prevent silent failures.
"""

from .data_contracts import DailyFrameSpec, IntradayFrameSpec
from .signal_schema import SignalOutputSpec
from .order_schema import OrderSchema

__all__ = [
    'DailyFrameSpec',
    'IntradayFrameSpec',
    'SignalOutputSpec',
    'OrderSchema'
]
